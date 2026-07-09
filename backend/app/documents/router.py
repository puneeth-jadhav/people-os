import csv
import io
import uuid

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, in_manager_chain, require_role
from app.events.dispatcher import emit
from app.parse.extractor import extract_text
from app.parse.parser import parse_document
from app.shared.audit import audit
from app.shared.models import Document, DocumentAcknowledgement, Employee
from app.shared.notifications import notify
from app.shared.responses import ApiError, ok
from app.shared.storage import create_signed_url, upload_file

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


def _can_view_document(db: Session, user: Employee, doc: Document) -> bool:
    """Authorization for a single document.

    Personal docs (doc_category='personal', owner_id set): the owner, anyone in
    the owner's manager chain, or an hr_admin may view.
    Policy/company docs (owner_id null): visible when the user's role is in
    visible_roles, or when visible_roles is null/empty (visible to all roles).
    """
    if doc.doc_category == "personal" and doc.owner_id is not None:
        if str(doc.owner_id) == str(user.id):
            return True
        if user.role == "hr_admin":
            return True
        return in_manager_chain(db, user.id, doc.owner_id)
    # Policy / company document.
    roles = doc.visible_roles
    if not roles:
        return True
    return user.role in roles


def _is_acknowledged(db: Session, document_id, employee_id) -> bool:
    return (
        db.query(DocumentAcknowledgement.id)
        .filter(
            DocumentAcknowledgement.document_id == document_id,
            DocumentAcknowledgement.employee_id == employee_id,
        )
        .first()
        is not None
    )


def _serialize(doc: Document, db: Session, user: Employee) -> dict:
    acknowledged = None
    if doc.requires_ack:
        acknowledged = _is_acknowledged(db, doc.id, user.id)
    return {
        "id": str(doc.id),
        "ownerId": str(doc.owner_id) if doc.owner_id else None,
        "docCategory": doc.doc_category,
        "docType": doc.doc_type,
        "title": doc.title,
        "version": doc.version,
        "changeSummary": doc.change_summary,
        "requiresAck": bool(doc.requires_ack),
        "visibleRoles": list(doc.visible_roles) if doc.visible_roles else None,
        "createdAt": doc.created_at.isoformat() if doc.created_at else None,
        "acknowledged": acknowledged,
    }


@router.get("")
def list_documents(
    category: str | None = None,
    page: int = 1,
    limit: int = 50,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List documents the current user is permitted to see. Titles the user
    cannot access are never leaked."""
    q = db.query(Document)
    if category:
        q = q.filter(Document.doc_category == category)
    q = q.order_by(Document.created_at.desc())
    rows = q.all()
    permitted = [d for d in rows if _can_view_document(db, user, d)]

    page = max(page, 1)
    limit = max(min(limit, 200), 1)
    start = (page - 1) * limit
    window = permitted[start : start + limit]
    return ok([_serialize(d, db, user) for d in window])


@router.post("/parse")
async def parse_document_endpoint(
    file: UploadFile = File(...),
    user: Employee = Depends(get_current_user),
):
    """Extract structured fields from an uploaded document. Does not persist."""
    try:
        file_bytes = await file.read()
    except Exception:
        file_bytes = b""

    text_content = extract_text(file_bytes, file.filename or "")
    result = parse_document(text_content)
    return ok(result)


@router.get("/search")
def search_documents(
    q: str | None = None,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Permission-scoped full-text search. Uses Postgres websearch_to_tsquery
    against the generated search_tsv, then filters out any documents the caller
    is not authorized to view (no title/snippet leakage)."""
    query = (q or "").strip()
    if not query:
        return ok([])

    tsquery = func.websearch_to_tsquery("english", query)
    rows = (
        db.query(
            Document,
            func.ts_headline(
                "english",
                func.coalesce(Document.content_text, ""),
                tsquery,
                text("'MaxWords=20, MinWords=5, ShortWord=2'"),
            ).label("snippet"),
        )
        .filter(Document.search_tsv.op("@@")(tsquery))
        .order_by(Document.created_at.desc())
        .all()
    )

    results = []
    for doc, snippet in rows:
        if not _can_view_document(db, user, doc):
            continue
        results.append(
            {
                "id": str(doc.id),
                "title": doc.title,
                "docType": doc.doc_type,
                "docCategory": doc.doc_category,
                "version": doc.version,
                "snippet": snippet,
            }
        )
    return ok(results)


@router.get("/acks/export")
def export_acknowledgements(
    user: Employee = Depends(require_role("hr_admin")),
    db: Session = Depends(get_db),
):
    """HR-only CSV export of acknowledgements across requires_ack policies."""
    rows = (
        db.query(
            Document.title,
            Document.version,
            Employee.name,
            DocumentAcknowledgement.acknowledged_at,
        )
        .join(
            DocumentAcknowledgement,
            DocumentAcknowledgement.document_id == Document.id,
        )
        .join(Employee, Employee.id == DocumentAcknowledgement.employee_id)
        .filter(Document.requires_ack.is_(True))
        .order_by(Document.title, Employee.name)
        .all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["documentTitle", "version", "employeeName", "acknowledgedAt"])
    for title, version, emp_name, acked_at in rows:
        writer.writerow(
            [
                title or "",
                version if version is not None else "",
                emp_name or "",
                acked_at.isoformat() if acked_at else "",
            ]
        )
    audit(
        db,
        actor_id=user.id,
        action="document.acks_exported",
        resource_type="document",
        resource_id=None,
        metadata={"count": len(rows)},
        commit=True,
    )
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=acknowledgements.csv"},
    )


@router.get("/{document_id}")
def get_document(
    document_id: str,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id).one_or_none()
    if doc is None:
        raise ApiError(404, "Document not found")
    if not _can_view_document(db, user, doc):
        raise ApiError(403, "You are not authorized to view this document")
    return ok(_serialize(doc, db, user))


@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    doc_category: str = Form(...),
    doc_type: str = Form(...),
    owner_id: str | None = Form(None),
    visible_roles: str | None = Form(None),
    requires_ack: str | None = Form(None),
    change_summary: str | None = Form(None),
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a private personal document or publish a policy.

    - personal: hr_admin (any owner), a manager for their reports, or the owner.
    - policy: hr_admin only. Publishing a policy of an existing doc_type creates
      a NEW row with an incremented version so history is retained; affected
      roles are notified with the version + change summary.
    """
    if doc_category not in ("personal", "policy"):
        raise ApiError(422, "docCategory must be 'personal' or 'policy'")
    if not title:
        raise ApiError(422, "title is required")

    ack_flag = str(requires_ack or "").lower() in ("1", "true", "yes", "on")
    roles_list = None
    if visible_roles:
        roles_list = [r.strip() for r in visible_roles.split(",") if r.strip()]

    resolved_owner = None
    if doc_category == "personal":
        resolved_owner = owner_id or str(user.id)
        # Authorization: hr_admin any; owner themselves; a manager of the owner.
        if user.role == "hr_admin":
            pass
        elif str(resolved_owner) == str(user.id):
            pass
        elif in_manager_chain(db, user.id, resolved_owner):
            pass
        else:
            raise ApiError(
                403, "You are not authorized to upload a document for this owner"
            )
    else:
        # Policy publish is hr_admin only.
        if user.role != "hr_admin":
            raise ApiError(403, "Only HR can publish policy documents")

    try:
        file_bytes = await file.read()
    except Exception:
        file_bytes = b""
    if not file_bytes:
        raise ApiError(422, "Empty file upload")

    name = file.filename or "document"
    ext = ""
    if "." in name:
        ext = "." + name.rsplit(".", 1)[1].lower()
    key = f"documents/{doc_category}/{uuid.uuid4().hex}{ext}"
    stored_path = upload_file(
        key, file_bytes, content_type=file.content_type or "application/octet-stream"
    )
    content_text = extract_text(file_bytes, name)

    # Policy versioning: new row with max(existing)+1 for the same doc_type.
    version = 1
    if doc_category == "policy":
        max_version = (
            db.query(func.max(Document.version))
            .filter(
                Document.doc_category == "policy",
                Document.doc_type == doc_type,
            )
            .scalar()
        )
        if max_version:
            version = int(max_version) + 1

    doc = Document(
        owner_id=resolved_owner,
        doc_category=doc_category,
        doc_type=doc_type,
        title=title,
        version=version,
        change_summary=change_summary,
        storage_path=stored_path,
        content_text=content_text,
        visible_roles=roles_list,
        requires_ack=ack_flag,
        uploaded_by=user.id,
    )
    db.add(doc)
    db.flush()

    if doc_category == "policy":
        # Notify every employee whose role is in visible_roles (or all when
        # visible_roles is empty). Title includes version + change summary.
        target_roles = roles_list
        recipients_q = db.query(Employee.id)
        if target_roles:
            recipients_q = recipients_q.filter(Employee.role.in_(target_roles))
        recipients = [rid for (rid,) in recipients_q.all()]

        summary = change_summary or ""
        ack_hint = " Please acknowledge." if ack_flag else ""
        notif_title = f"{title} (v{version}) published"
        notif_body = (
            f"{summary}{ack_hint}".strip()
            or f"A new version (v{version}) has been published.{ack_hint}"
        )
        for rid in recipients:
            notify(
                db,
                recipient_id=rid,
                type="policy.published",
                title=notif_title,
                body=notif_body,
                link="/documents",
                resource_type="document",
                resource_id=doc.id,
                commit=False,
            )
        audit(
            db,
            actor_id=user.id,
            action="policy.published",
            resource_type="document",
            resource_id=doc.id,
            metadata={
                "docType": doc_type,
                "version": version,
                "changeSummary": summary,
                "requiresAck": ack_flag,
            },
            commit=False,
        )
        db.commit()
        db.refresh(doc)
        emit(
            "policy.published",
            {"documentId": str(doc.id), "version": version},
            db,
        )
    else:
        audit(
            db,
            actor_id=user.id,
            action="document.uploaded",
            resource_type="document",
            resource_id=doc.id,
            metadata={"docType": doc_type, "ownerId": str(resolved_owner)},
            commit=False,
        )
        db.commit()
        db.refresh(doc)

    return ok(_serialize(doc, db, user))


@router.get("/{document_id}/download")
def download_document(
    document_id: str,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a short-lived signed URL for a document. Authorization enforced;
    never returns a permanent public URL."""
    doc = db.query(Document).filter(Document.id == document_id).one_or_none()
    if doc is None:
        raise ApiError(404, "Document not found")
    if not _can_view_document(db, user, doc):
        raise ApiError(403, "You are not authorized to download this document")
    if not doc.storage_path:
        raise ApiError(404, "No file attached to this document")

    signed_url = create_signed_url(doc.storage_path, expires_in=120)
    audit(
        db,
        actor_id=user.id,
        action="document.downloaded",
        resource_type="document",
        resource_id=doc.id,
        metadata={"docType": doc.doc_type},
        commit=True,
    )
    emit("document.downloaded", {"documentId": str(doc.id)}, db)
    return ok({"url": signed_url, "expiresIn": 120})


@router.post("/{document_id}/acknowledge")
def acknowledge_document(
    document_id: str,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Acknowledge a policy document. Idempotent — returns 200 even if the
    document was already acknowledged by this user."""
    doc = db.query(Document).filter(Document.id == document_id).one_or_none()
    if doc is None:
        raise ApiError(404, "Document not found")
    if doc.doc_category != "policy":
        raise ApiError(409, "Only policy documents can be acknowledged")
    if not _can_view_document(db, user, doc):
        raise ApiError(403, "You are not authorized to acknowledge this document")

    existing = (
        db.query(DocumentAcknowledgement)
        .filter(
            DocumentAcknowledgement.document_id == doc.id,
            DocumentAcknowledgement.employee_id == user.id,
        )
        .one_or_none()
    )
    if existing is None:
        db.add(
            DocumentAcknowledgement(document_id=doc.id, employee_id=user.id)
        )
        audit(
            db,
            actor_id=user.id,
            action="policy.acknowledged",
            resource_type="document",
            resource_id=doc.id,
            metadata={"docType": doc.doc_type, "version": doc.version},
            commit=False,
        )
        db.commit()
        emit(
            "policy.acknowledged",
            {"documentId": str(doc.id), "employeeId": str(user.id)},
            db,
        )
    return ok({"documentId": str(doc.id), "acknowledged": True})
