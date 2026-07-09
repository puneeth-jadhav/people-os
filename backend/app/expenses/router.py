import csv
import io
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, in_manager_chain, require_role
from app.events.dispatcher import emit
from app.parse.extractor import extract_text
from app.parse.parser import parse_document
from app.shared.audit import audit
from app.shared.models import Employee, Expense
from app.shared.notifications import notify
from app.shared.responses import ApiError, CamelModel, ok
from app.shared.storage import create_signed_url, upload_file

router = APIRouter(prefix="/api/v1/expenses", tags=["expenses"])

# Expenses at or above this amount require a second (finance) approval after
# the manager signs off. Below it, a manager approval pays out directly.
FINANCE_THRESHOLD = 10000.0


class ExpenseCreate(CamelModel):
    amount: float
    category: str
    description: str | None = None
    expense_date: date | None = None
    receipt_path: str | None = None


class ExpenseDecision(CamelModel):
    decision_note: str | None = None


def _employee_name(db: Session, emp_id) -> str:
    if emp_id is None:
        return "Employee"
    row = db.query(Employee.name).filter(Employee.id == emp_id).one_or_none()
    return row[0] if row and row[0] else "Employee"


def _serialize(e: Expense, db: Session) -> dict:
    # Receipt bytes are private: do NOT embed a signed URL here. Callers must
    # fetch a short-lived signed URL via GET /expenses/{id}/receipt, which
    # enforces authorization and writes a download audit entry.
    return {
        "id": str(e.id),
        "employeeId": str(e.employee_id),
        "employeeName": _employee_name(db, e.employee_id),
        "amount": float(e.amount) if e.amount is not None else None,
        "category": e.category,
        "description": e.description,
        "expenseDate": e.expense_date.isoformat() if e.expense_date else None,
        "hasReceipt": bool(e.receipt_path),
        "status": e.status,
        "approverId": str(e.approver_id) if e.approver_id else None,
        "financeApproverId": (
            str(e.finance_approver_id) if e.finance_approver_id else None
        ),
        "requiresFinance": float(e.amount or 0) >= FINANCE_THRESHOLD,
        "submittedAt": e.submitted_at.isoformat() if e.submitted_at else None,
        "resolvedAt": e.resolved_at.isoformat() if e.resolved_at else None,
    }


def _authorize_manager_decision(db: Session, e: Expense, user: Employee) -> None:
    """Manager-stage decisions: hr_admin or someone in the claimant's chain.
    Blocks self-approval and out-of-chain managers."""
    if str(e.employee_id) == str(user.id):
        raise ApiError(403, "You cannot decide on your own expense")
    if user.role == "hr_admin":
        return
    if in_manager_chain(db, user.id, e.employee_id):
        return
    raise ApiError(403, "You are not authorized to decide on this expense")


@router.post("")
@router.post("/")
def create_expense(
    body: ExpenseCreate,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.amount is None or body.amount <= 0:
        raise ApiError(422, "amount must be greater than 0")
    if not body.category:
        raise ApiError(422, "category is required")

    # HR admins are the approval/finance authority, so their own expenses are
    # auto-approved and marked paid immediately — there is no separate approver
    # to route to (and no self-approval concern).
    if user.role == "hr_admin":
        e = Expense(
            employee_id=user.id,
            amount=body.amount,
            category=body.category,
            description=body.description,
            expense_date=body.expense_date or date.today(),
            receipt_path=body.receipt_path,
            status="paid",
            approver_id=user.id,
            finance_approver_id=user.id,
            submitted_at=datetime.now(timezone.utc),
            resolved_at=datetime.now(timezone.utc),
        )
        db.add(e)
        db.flush()

        notify(
            db,
            recipient_id=user.id,
            type="expense.updated",
            title="Expense auto-approved and marked paid",
            body=f"₹{body.amount:g} — {body.category}"
            + (f" — {body.description}" if body.description else ""),
            link=f"/expenses?expenseId={e.id}",
            resource_type="expense",
            resource_id=e.id,
            commit=False,
        )
        audit(
            db,
            actor_id=user.id,
            action="expense.auto_approved",
            resource_type="expense",
            resource_id=e.id,
            metadata={
                "amount": float(body.amount),
                "category": body.category,
                "reason": "hr_admin self-expense",
            },
            commit=False,
        )
        db.commit()
        db.refresh(e)
        emit(
            "expense.manager_approved",
            {"expenseId": str(e.id)},
            db,
        )
        return ok(_serialize(e, db))

    approver_id = user.manager_id
    if approver_id is None:
        raise ApiError(409, "No manager assigned to approve this expense")

    e = Expense(
        employee_id=user.id,
        amount=body.amount,
        category=body.category,
        description=body.description,
        expense_date=body.expense_date or date.today(),
        receipt_path=body.receipt_path,
        status="pending_manager",
        approver_id=approver_id,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(e)
    db.flush()

    notify(
        db,
        recipient_id=approver_id,
        type="expense.submitted",
        title=f"{_employee_name(db, user.id)} submitted a ₹{body.amount:g} expense",
        body=f"{body.category}" + (f" — {body.description}" if body.description else ""),
        link=f"/expenses?expenseId={e.id}",
        resource_type="expense",
        resource_id=e.id,
        commit=False,
    )
    audit(
        db,
        actor_id=user.id,
        action="expense.submitted",
        resource_type="expense",
        resource_id=e.id,
        metadata={"amount": float(body.amount), "category": body.category},
        commit=False,
    )
    db.commit()
    db.refresh(e)
    emit(
        "expense.submitted",
        {"expenseId": str(e.id), "employeeId": str(user.id)},
        db,
    )
    return ok(_serialize(e, db))


@router.post("/parse")
async def parse_receipt(
    file: UploadFile = File(...),
    user: Employee = Depends(get_current_user),
):
    """Extract structured fields from a receipt to auto-fill the expense form.
    Does NOT persist an expense — extraction only."""
    try:
        file_bytes = await file.read()
    except Exception:
        file_bytes = b""
    text = extract_text(file_bytes, file.filename or "")
    parsed = parse_document(text)
    return ok(parsed)


@router.post("/upload-receipt")
async def upload_receipt(
    file: UploadFile = File(...),
    parse: str = Form("true"),
    user: Employee = Depends(get_current_user),
):
    """Store a receipt file and (optionally) return parsed auto-fill fields.
    Returns the storage path to attach when creating the expense."""
    try:
        file_bytes = await file.read()
    except Exception:
        file_bytes = b""
    if not file_bytes:
        raise ApiError(422, "Empty file upload")

    ext = ""
    name = file.filename or "receipt"
    if "." in name:
        ext = "." + name.rsplit(".", 1)[1].lower()
    key = f"receipts/{user.id}/{uuid.uuid4().hex}{ext}"
    stored_path = upload_file(
        key, file_bytes, content_type=file.content_type or "application/octet-stream"
    )

    result: dict = {"receiptPath": stored_path}
    if str(parse).lower() in ("1", "true", "yes"):
        text = extract_text(file_bytes, name)
        result["parsed"] = parse_document(text)
    return ok(result)


@router.get("")
def list_expenses(
    scope: str = "mine",
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List expenses. scope=mine (default) returns the caller's own claims."""
    rows = (
        db.query(Expense)
        .filter(Expense.employee_id == user.id)
        .order_by(Expense.submitted_at.desc())
        .all()
    )
    return ok([_serialize(e, db) for e in rows])


@router.get("/queue")
def manager_queue(
    user: Employee = Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    """Expenses awaiting the current manager's first-stage approval."""
    rows = (
        db.query(Expense)
        .filter(
            Expense.approver_id == user.id,
            Expense.status == "pending_manager",
        )
        .order_by(Expense.submitted_at.desc())
        .all()
    )
    return ok([_serialize(e, db) for e in rows])


@router.get("/finance-queue")
def finance_queue(
    user: Employee = Depends(require_role("hr_admin")),
    db: Session = Depends(get_db),
):
    """Expenses awaiting finance sign-off after manager approval."""
    rows = (
        db.query(Expense)
        .filter(Expense.status == "pending_finance")
        .order_by(Expense.submitted_at.desc())
        .all()
    )
    return ok([_serialize(e, db) for e in rows])


@router.get("/finance/export")
def finance_export(
    user: Employee = Depends(require_role("hr_admin")),
    db: Session = Depends(get_db),
):
    """Export paid + pending-finance expenses as CSV (finance/HR only)."""
    rows = (
        db.query(Expense)
        .filter(Expense.status.in_(["paid", "pending_finance"]))
        .order_by(Expense.submitted_at.desc())
        .all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "employee",
            "amount",
            "category",
            "description",
            "expenseDate",
            "status",
            "submittedAt",
            "resolvedAt",
        ]
    )
    for e in rows:
        writer.writerow(
            [
                str(e.id),
                _employee_name(db, e.employee_id),
                float(e.amount) if e.amount is not None else "",
                e.category or "",
                e.description or "",
                e.expense_date.isoformat() if e.expense_date else "",
                e.status,
                e.submitted_at.isoformat() if e.submitted_at else "",
                e.resolved_at.isoformat() if e.resolved_at else "",
            ]
        )
    audit(
        db,
        actor_id=user.id,
        action="expense.exported",
        resource_type="expense",
        resource_id=None,
        metadata={"count": len(rows)},
        commit=True,
    )
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"},
    )


@router.post("/{expense_id}/manager-approve")
def manager_approve(
    expense_id: str,
    body: ExpenseDecision | None = None,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    e = db.query(Expense).filter(Expense.id == expense_id).one_or_none()
    if e is None:
        raise ApiError(404, "Expense not found")
    _authorize_manager_decision(db, e, user)
    if e.status != "pending_manager":
        raise ApiError(409, f"Expense already {e.status}")

    note = body.decision_note if body else None
    e.approver_id = user.id
    amount = float(e.amount or 0)

    # Both branches record the manager decision under the same audit action
    # and event name, per contract; the resulting status differs by threshold.
    audit_action = "expense.manager_approved"
    emit_event = "expense.manager_approved"
    if amount >= FINANCE_THRESHOLD:
        # Threshold routing: escalate to finance for a second approval.
        e.status = "pending_finance"
        # Notify all finance/HR admins.
        for (admin_id,) in db.query(Employee.id).filter(
            Employee.role == "hr_admin"
        ).all():
            notify(
                db,
                recipient_id=admin_id,
                type="expense.pending_finance",
                title=f"Expense ₹{amount:g} needs finance approval",
                body=f"{_employee_name(db, e.employee_id)} — {e.category}",
                link=f"/expenses?expenseId={e.id}",
                resource_type="expense",
                resource_id=e.id,
                commit=False,
            )
        emp_title = "Expense approved by manager — pending finance"
    else:
        # Below threshold: manager approval pays it out directly.
        e.status = "paid"
        e.resolved_at = datetime.now(timezone.utc)
        emp_title = "Expense approved and marked paid"

    notify(
        db,
        recipient_id=e.employee_id,
        type="expense.updated",
        title=emp_title,
        body=f"₹{amount:g} — {e.category}"
        + (f" Note: {note}" if note else ""),
        link=f"/expenses?expenseId={e.id}",
        resource_type="expense",
        resource_id=e.id,
        commit=False,
    )
    audit(
        db,
        actor_id=user.id,
        action=audit_action,
        resource_type="expense",
        resource_id=e.id,
        metadata={"amount": amount, "status": e.status},
        commit=False,
    )
    db.commit()
    db.refresh(e)
    emit(emit_event, {"expenseId": str(e.id)}, db)
    return ok(_serialize(e, db))


@router.post("/{expense_id}/finance-approve")
def finance_approve(
    expense_id: str,
    body: ExpenseDecision | None = None,
    user: Employee = Depends(require_role("hr_admin")),
    db: Session = Depends(get_db),
):
    e = db.query(Expense).filter(Expense.id == expense_id).one_or_none()
    if e is None:
        raise ApiError(404, "Expense not found")
    if str(e.employee_id) == str(user.id):
        raise ApiError(403, "You cannot decide on your own expense")
    if e.status != "pending_finance":
        raise ApiError(409, f"Expense is {e.status}, not pending finance")

    note = body.decision_note if body else None
    e.status = "paid"
    e.finance_approver_id = user.id
    e.resolved_at = datetime.now(timezone.utc)
    amount = float(e.amount or 0)

    notify(
        db,
        recipient_id=e.employee_id,
        type="expense.updated",
        title="Expense approved by finance and marked paid",
        body=f"₹{amount:g} — {e.category}"
        + (f" Note: {note}" if note else ""),
        link=f"/expenses?expenseId={e.id}",
        resource_type="expense",
        resource_id=e.id,
        commit=False,
    )
    audit(
        db,
        actor_id=user.id,
        action="expense.finance_approved",
        resource_type="expense",
        resource_id=e.id,
        metadata={"amount": amount, "stage": "finance"},
        commit=False,
    )
    db.commit()
    db.refresh(e)
    emit("expense.finance_approved", {"expenseId": str(e.id)}, db)
    return ok(_serialize(e, db))


@router.post("/{expense_id}/reject")
def reject_expense(
    expense_id: str,
    body: ExpenseDecision | None = None,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    e = db.query(Expense).filter(Expense.id == expense_id).one_or_none()
    if e is None:
        raise ApiError(404, "Expense not found")
    if e.status in ("paid", "rejected"):
        raise ApiError(409, f"Expense already {e.status}")

    # Finance can reject at the finance stage; manager-chain / hr_admin at
    # the manager stage.
    if e.status == "pending_finance":
        if user.role != "hr_admin":
            raise ApiError(403, "Only finance can reject at this stage")
        if str(e.employee_id) == str(user.id):
            raise ApiError(403, "You cannot decide on your own expense")
    else:
        _authorize_manager_decision(db, e, user)

    note = body.decision_note if body else None
    e.status = "rejected"
    e.resolved_at = datetime.now(timezone.utc)
    amount = float(e.amount or 0)

    notify(
        db,
        recipient_id=e.employee_id,
        type="expense.updated",
        title="Expense rejected",
        body=f"₹{amount:g} — {e.category}"
        + (f" Note: {note}" if note else ""),
        link=f"/expenses?expenseId={e.id}",
        resource_type="expense",
        resource_id=e.id,
        commit=False,
    )
    audit(
        db,
        actor_id=user.id,
        action="expense.rejected",
        resource_type="expense",
        resource_id=e.id,
        metadata={"amount": amount},
        commit=False,
    )
    db.commit()
    db.refresh(e)
    emit("expense.rejected", {"expenseId": str(e.id)}, db)
    return ok(_serialize(e, db))


@router.get("/{expense_id}/receipt")
def get_receipt(
    expense_id: str,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a short-lived signed URL for a receipt. Authorized to the owner,
    anyone in the claimant's manager chain, or HR/finance. Never public."""
    e = db.query(Expense).filter(Expense.id == expense_id).one_or_none()
    if e is None:
        raise ApiError(404, "Expense not found")
    authorized = (
        str(e.employee_id) == str(user.id)
        or user.role == "hr_admin"
        or in_manager_chain(db, user.id, e.employee_id)
    )
    if not authorized:
        raise ApiError(403, "You are not authorized to view this receipt")
    if not e.receipt_path:
        raise ApiError(404, "No receipt attached to this expense")

    signed_url = create_signed_url(e.receipt_path, expires_in=300)
    audit(
        db,
        actor_id=user.id,
        action="document.downloaded",
        resource_type="expense",
        resource_id=e.id,
        metadata={"receiptPath": e.receipt_path},
        commit=True,
    )
    return ok({"receiptUrl": signed_url, "expiresIn": 300})
