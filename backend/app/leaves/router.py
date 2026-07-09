from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, in_manager_chain, require_role
from app.events.dispatcher import emit
from app.shared.audit import audit
from app.shared.models import Employee, LeaveBalance, LeaveRequest, LeaveRule
from app.shared.notifications import notify
from app.shared.responses import ApiError, CamelModel, ok

router = APIRouter(prefix="/api/v1/leaves", tags=["leaves"])


class LeaveRequestCreate(CamelModel):
    request_type: str = "leave"  # 'leave' | 'wfh'
    leave_type: str | None = None  # required when request_type == 'leave'
    start_date: date
    end_date: date
    reason: str | None = None


class LeaveDecision(CamelModel):
    decision_note: str | None = None


class LeaveRuleItem(CamelModel):
    leave_type: str
    annual_quota: float
    accrual_per_month: float | None = None
    carry_forward_max: float | None = None
    active: bool = True


def _business_days(start: date, end: date) -> int:
    """Count Mon–Fri days between start and end inclusive (excludes weekends)."""
    if end < start:
        return 0
    total = 0
    cur = start
    while cur <= end:
        if cur.weekday() < 5:  # 0=Mon .. 4=Fri
            total += 1
        cur += timedelta(days=1)
    return total


def _employee_name(db: Session, emp_id) -> str:
    row = db.query(Employee.name).filter(Employee.id == emp_id).one_or_none()
    return row[0] if row and row[0] else "Employee"


def _serialize(r: LeaveRequest, db: Session) -> dict:
    return {
        "id": str(r.id),
        "employeeId": str(r.employee_id),
        "employeeName": _employee_name(db, r.employee_id),
        "requestType": r.request_type,
        "leaveType": r.leave_type,
        "startDate": r.start_date.isoformat() if r.start_date else None,
        "endDate": r.end_date.isoformat() if r.end_date else None,
        "daysRequested": float(r.days_requested) if r.days_requested is not None else None,
        "status": r.status,
        "approverId": str(r.approver_id) if r.approver_id else None,
        "reason": r.reason,
        "decisionNote": r.decision_note,
        "appliedAt": r.applied_at.isoformat() if r.applied_at else None,
        "resolvedAt": r.resolved_at.isoformat() if r.resolved_at else None,
    }


def _serialize_balance(b: LeaveBalance) -> dict:
    total = float(b.total_days or 0) + float(b.carry_forward_days or 0)
    used = float(b.used_days or 0)
    pending = float(b.pending_days or 0)
    return {
        "id": str(b.id),
        "leaveType": b.leave_type,
        "year": b.year,
        "total": total,
        "used": used,
        "pending": pending,
        "carryForward": float(b.carry_forward_days or 0),
        "remaining": total - used - pending,
    }


def _team_overlap(db: Session, user: Employee, start: date, end: date) -> list[dict]:
    """Reports of the same manager with approved/pending requests overlapping [start, end]."""
    if user.manager_id is None:
        return []
    rows = (
        db.query(LeaveRequest, Employee.name)
        .join(Employee, Employee.id == LeaveRequest.employee_id)
        .filter(
            Employee.manager_id == user.manager_id,
            LeaveRequest.employee_id != user.id,
            LeaveRequest.status.in_(("pending", "approved")),
            LeaveRequest.start_date <= end,
            LeaveRequest.end_date >= start,
        )
        .order_by(LeaveRequest.start_date.asc())
        .all()
    )
    return [
        {
            "employeeName": name or "Colleague",
            "startDate": r.start_date.isoformat() if r.start_date else None,
            "endDate": r.end_date.isoformat() if r.end_date else None,
            "requestType": r.request_type,
        }
        for (r, name) in rows
    ]


@router.get("/balances")
def get_balances(
    user: Employee = Depends(get_current_user), db: Session = Depends(get_db)
):
    year = date.today().year
    rows = (
        db.query(LeaveBalance)
        .filter(
            LeaveBalance.employee_id == user.id,
            LeaveBalance.year == year,
        )
        .all()
    )
    return ok([_serialize_balance(b) for b in rows])


@router.post("")
@router.post("/")
def create_leave_request(
    body: LeaveRequestCreate,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.request_type not in ("leave", "wfh"):
        raise ApiError(422, "requestType must be 'leave' or 'wfh'")
    if body.end_date < body.start_date:
        raise ApiError(422, "endDate must be on or after startDate")

    days = _business_days(body.start_date, body.end_date)
    if days <= 0:
        raise ApiError(422, "Request must span at least one business day")

    approver_id = user.manager_id
    if approver_id is None:
        raise ApiError(409, "No manager assigned to approve this request")

    year = date.today().year
    balance = None
    if body.request_type == "leave":
        if not body.leave_type:
            raise ApiError(422, "leaveType is required for leave requests")
        rule = (
            db.query(LeaveRule)
            .filter(LeaveRule.leave_type == body.leave_type, LeaveRule.active.is_(True))
            .one_or_none()
        )
        if rule is None:
            raise ApiError(422, f"Unknown leave type '{body.leave_type}'")
        balance = (
            db.query(LeaveBalance)
            .filter(
                LeaveBalance.employee_id == user.id,
                LeaveBalance.leave_type == body.leave_type,
                LeaveBalance.year == year,
            )
            .one_or_none()
        )
        if balance is None:
            raise ApiError(422, "No leave balance on record for this type")
        total = float(balance.total_days or 0) + float(balance.carry_forward_days or 0)
        available = total - float(balance.used_days or 0) - float(balance.pending_days or 0)
        if days > available:
            raise ApiError(
                409,
                f"Insufficient balance: {days} requested, {available:g} available",
            )

    overlap = _team_overlap(db, user, body.start_date, body.end_date)

    req = LeaveRequest(
        employee_id=user.id,
        request_type=body.request_type,
        leave_type=body.leave_type if body.request_type == "leave" else None,
        start_date=body.start_date,
        end_date=body.end_date,
        days_requested=days,
        status="pending",
        approver_id=approver_id,
        reason=body.reason,
        applied_at=datetime.now(timezone.utc),
    )
    db.add(req)

    # Reserve pending days on the balance for leave (never WFH).
    if balance is not None:
        balance.pending_days = float(balance.pending_days or 0) + days

    db.flush()

    if req.request_type == "wfh":
        label = "WFH"
        title = f"{_employee_name(db, user.id)} requested {days} day WFH"
        audit_action = "wfh.submitted"
    else:
        label = f"{(req.leave_type or 'leave').title()} leave"
        title = f"{_employee_name(db, user.id)} requested {days} day {label}"
        audit_action = "leave.submitted"

    notify(
        db,
        recipient_id=approver_id,
        type="request.submitted",
        title=title,
        body=f"{req.start_date.isoformat()} → {req.end_date.isoformat()}"
        + (f" — {req.reason}" if req.reason else ""),
        link=f"/approvals?requestId={req.id}",
        resource_type="leave_request",
        resource_id=req.id,
        commit=False,
    )
    audit(
        db,
        actor_id=user.id,
        action=audit_action,
        resource_type="leave_request",
        resource_id=req.id,
        metadata={"requestType": req.request_type, "days": days},
        commit=False,
    )
    db.commit()
    db.refresh(req)
    emit(
        "request.submitted",
        {"requestId": str(req.id), "employeeId": str(user.id)},
        db,
    )
    result = _serialize(req, db)
    result["teamOverlap"] = overlap
    return ok(result)


@router.get("/mine")
def list_my_requests(
    page: int = 1,
    limit: int = 50,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page = max(1, page)
    limit = max(1, min(limit, 200))
    rows = (
        db.query(LeaveRequest)
        .filter(LeaveRequest.employee_id == user.id)
        .order_by(LeaveRequest.applied_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return ok([_serialize(r, db) for r in rows])


@router.get("/queue")
def approval_queue(
    user: Employee = Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    """Pending requests where the current user is the assigned approver."""
    rows = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.approver_id == user.id,
            LeaveRequest.status == "pending",
        )
        .order_by(LeaveRequest.applied_at.desc())
        .all()
    )
    return ok([_serialize(r, db) for r in rows])


@router.get("/calendar")
def team_calendar(
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approved (+pending) leave/WFH for the user's team within a date range."""
    today = date.today()
    start = from_ or today.replace(day=1)
    end = to or (start + timedelta(days=60))

    # Team = the user's direct reports + self.
    report_ids = [
        row[0]
        for row in db.query(Employee.id)
        .filter(Employee.manager_id == user.id)
        .all()
    ]
    team_ids = set(report_ids)
    team_ids.add(user.id)

    rows = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.employee_id.in_(team_ids),
            LeaveRequest.status.in_(("approved", "pending")),
            LeaveRequest.start_date <= end,
            LeaveRequest.end_date >= start,
        )
        .order_by(LeaveRequest.start_date.asc())
        .all()
    )
    return ok([_serialize(r, db) for r in rows])


def _authorize_decision(db: Session, req: LeaveRequest, user: Employee) -> None:
    """Manager role alone is NOT enough: require manager-chain or hr_admin.
    Block employees, self-approval and out-of-chain managers."""
    if str(req.employee_id) == str(user.id):
        raise ApiError(403, "You cannot decide on your own request")
    if user.role == "hr_admin":
        return
    if in_manager_chain(db, user.id, req.employee_id):
        return
    raise ApiError(403, "You are not authorized to decide on this request")


@router.post("/{request_id}/approve")
def approve_request(
    request_id: str,
    body: LeaveDecision | None = None,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    req = db.query(LeaveRequest).filter(LeaveRequest.id == request_id).one_or_none()
    if req is None:
        raise ApiError(404, "Request not found")
    _authorize_decision(db, req, user)
    if req.status != "pending":
        raise ApiError(409, f"Request already {req.status}")

    note = body.decision_note if body else None

    if req.request_type == "leave" and req.leave_type:
        year = req.start_date.year if req.start_date else date.today().year
        # Lock the balance row to prevent concurrent overdraw.
        balance = (
            db.query(LeaveBalance)
            .filter(
                LeaveBalance.employee_id == req.employee_id,
                LeaveBalance.leave_type == req.leave_type,
                LeaveBalance.year == year,
            )
            .with_for_update()
            .one_or_none()
        )
        if balance is None:
            raise ApiError(409, "Leave balance no longer available")
        days = float(req.days_requested or 0)
        total = float(balance.total_days or 0) + float(balance.carry_forward_days or 0)
        # Available for approval = total - used (pending includes THIS request).
        available_after = total - float(balance.used_days or 0)
        if days > available_after:
            db.rollback()
            raise ApiError(
                409,
                f"Insufficient balance to approve: {days} needed, "
                f"{available_after:g} available",
            )
        balance.pending_days = max(0.0, float(balance.pending_days or 0) - days)
        balance.used_days = float(balance.used_days or 0) + days
        audit_action = "leave.approved"
        label = f"{(req.leave_type or 'leave').title()} leave"
    else:
        audit_action = "wfh.approved"
        label = "WFH"

    req.status = "approved"
    req.decision_note = note
    req.resolved_at = datetime.now(timezone.utc)

    notify(
        db,
        recipient_id=req.employee_id,
        type="request.approved",
        title=f"{label} request approved",
        body=f"Your {label} request ({req.start_date.isoformat()} → "
        f"{req.end_date.isoformat()}) was approved."
        + (f" Note: {note}" if note else ""),
        link=f"/requests?requestId={req.id}",
        resource_type="leave_request",
        resource_id=req.id,
        commit=False,
    )
    audit(
        db,
        actor_id=user.id,
        action=audit_action,
        resource_type="leave_request",
        resource_id=req.id,
        metadata={"requestType": req.request_type, "days": float(req.days_requested or 0)},
        commit=False,
    )
    db.commit()
    db.refresh(req)
    emit("request.approved", {"requestId": str(req.id)}, db)
    return ok(_serialize(req, db))


@router.post("/{request_id}/reject")
def reject_request(
    request_id: str,
    body: LeaveDecision | None = None,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    req = db.query(LeaveRequest).filter(LeaveRequest.id == request_id).one_or_none()
    if req is None:
        raise ApiError(404, "Request not found")
    _authorize_decision(db, req, user)
    if req.status != "pending":
        raise ApiError(409, f"Request already {req.status}")

    note = body.decision_note if body else None

    if req.request_type == "leave" and req.leave_type:
        year = req.start_date.year if req.start_date else date.today().year
        balance = (
            db.query(LeaveBalance)
            .filter(
                LeaveBalance.employee_id == req.employee_id,
                LeaveBalance.leave_type == req.leave_type,
                LeaveBalance.year == year,
            )
            .with_for_update()
            .one_or_none()
        )
        if balance is not None:
            days = float(req.days_requested or 0)
            balance.pending_days = max(0.0, float(balance.pending_days or 0) - days)
        audit_action = "leave.rejected"
        label = f"{(req.leave_type or 'leave').title()} leave"
    else:
        audit_action = "wfh.rejected"
        label = "WFH"

    req.status = "rejected"
    req.decision_note = note
    req.resolved_at = datetime.now(timezone.utc)

    notify(
        db,
        recipient_id=req.employee_id,
        type="request.rejected",
        title=f"{label} request rejected",
        body=f"Your {label} request was rejected."
        + (f" Note: {note}" if note else ""),
        link=f"/requests?requestId={req.id}",
        resource_type="leave_request",
        resource_id=req.id,
        commit=False,
    )
    audit(
        db,
        actor_id=user.id,
        action=audit_action,
        resource_type="leave_request",
        resource_id=req.id,
        metadata={"requestType": req.request_type},
        commit=False,
    )
    db.commit()
    db.refresh(req)
    emit("request.rejected", {"requestId": str(req.id)}, db)
    return ok(_serialize(req, db))


@router.put("/rules")
def update_leave_rules(
    body: list[LeaveRuleItem],
    user: Employee = Depends(require_role("hr_admin")),
    db: Session = Depends(get_db),
):
    """Upsert HR-editable leave quota rules."""
    result = []
    for item in body:
        rule = (
            db.query(LeaveRule)
            .filter(LeaveRule.leave_type == item.leave_type)
            .one_or_none()
        )
        if rule is None:
            rule = LeaveRule(leave_type=item.leave_type)
            db.add(rule)
        rule.annual_quota = item.annual_quota
        if item.accrual_per_month is not None:
            rule.accrual_per_month = item.accrual_per_month
        if item.carry_forward_max is not None:
            rule.carry_forward_max = item.carry_forward_max
        rule.active = item.active
        result.append(rule)
    db.flush()
    audit(
        db,
        actor_id=user.id,
        action="leave.rules_updated",
        resource_type="leave_rule",
        metadata={"count": len(result)},
        commit=False,
    )
    db.commit()
    return ok(
        [
            {
                "id": str(r.id),
                "leaveType": r.leave_type,
                "annualQuota": float(r.annual_quota or 0),
                "accrualPerMonth": float(r.accrual_per_month or 0),
                "carryForwardMax": float(r.carry_forward_max or 0),
                "active": bool(r.active),
            }
            for r in result
        ]
    )
