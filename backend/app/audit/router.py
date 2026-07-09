import csv
import io

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_role
from app.shared.audit import audit
from app.shared.models import AuditLog, Employee
from app.shared.responses import ok

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


def _actor_names(db: Session, actor_ids: list) -> dict:
    ids = [a for a in actor_ids if a is not None]
    if not ids:
        return {}
    rows = db.query(Employee.id, Employee.name).filter(Employee.id.in_(ids)).all()
    return {str(i): n for (i, n) in rows}


def _serialize(row: AuditLog, names: dict) -> dict:
    return {
        "id": str(row.id),
        "actorId": str(row.actor_id) if row.actor_id else None,
        "actorName": names.get(str(row.actor_id)) if row.actor_id else "System",
        "action": row.action,
        "resourceType": row.resource_type,
        "resourceId": str(row.resource_id) if row.resource_id else None,
        "metadata": row.metadata_,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("")
def list_audit(
    action: str | None = None,
    resource_type: str | None = None,
    page: int = 1,
    limit: int = 100,
    user: Employee = Depends(require_role("hr_admin")),
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    if resource_type:
        q = q.filter(AuditLog.resource_type == resource_type)
    page = max(page, 1)
    limit = max(min(limit, 500), 1)
    rows = (
        q.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    names = _actor_names(db, [r.actor_id for r in rows])
    return ok([_serialize(r, names) for r in rows])


@router.get("/export")
def export_audit(
    action: str | None = None,
    resource_type: str | None = None,
    user: Employee = Depends(require_role("hr_admin")),
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    if resource_type:
        q = q.filter(AuditLog.resource_type == resource_type)
    rows = q.order_by(AuditLog.created_at.desc()).all()
    names = _actor_names(db, [r.actor_id for r in rows])

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["createdAt", "actor", "action", "resourceType", "resourceId", "metadata"]
    )
    for r in rows:
        writer.writerow(
            [
                r.created_at.isoformat() if r.created_at else "",
                names.get(str(r.actor_id), "System") if r.actor_id else "System",
                r.action or "",
                r.resource_type or "",
                str(r.resource_id) if r.resource_id else "",
                r.metadata_ if r.metadata_ else "",
            ]
        )
    # Exporting sensitive data is itself an audited action.
    audit(
        db,
        actor_id=user.id,
        action="data.exported",
        resource_type="audit_log",
        resource_id=None,
        metadata={"count": len(rows)},
        commit=True,
    )
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
    )
