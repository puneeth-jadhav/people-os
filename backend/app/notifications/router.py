from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.shared.models import Employee, Notification
from app.shared.responses import ApiError, CamelModel, ok

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


class MarkReadBody(CamelModel):
    read: bool = True


def _serialize(n: Notification) -> dict:
    return {
        "id": str(n.id),
        "type": n.type,
        "title": n.title,
        "body": n.body,
        "link": n.link,
        "resourceType": n.resource_type,
        "resourceId": str(n.resource_id) if n.resource_id else None,
        "read": bool(n.read),
        "createdAt": n.created_at.isoformat() if n.created_at else None,
    }


@router.get("")
def list_notifications(
    type: str | None = None,
    unread: bool | None = None,
    page: int = 1,
    limit: int = 50,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Notification).filter(Notification.recipient_id == user.id)
    if type:
        q = q.filter(Notification.type == type)
    if unread:
        q = q.filter(Notification.read.is_(False))
    page = max(page, 1)
    limit = max(min(limit, 200), 1)
    rows = (
        q.order_by(Notification.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return ok([_serialize(n) for n in rows])


# Static paths MUST be declared before the dynamic /{notification_id} route
# so they are not shadowed by it.
@router.get("/unread-count")
def unread_count(
    user: Employee = Depends(get_current_user), db: Session = Depends(get_db)
):
    count = (
        db.query(Notification)
        .filter(
            Notification.recipient_id == user.id,
            Notification.read.is_(False),
        )
        .count()
    )
    return ok({"count": count})


@router.post("/read-all")
def mark_all_read(
    user: Employee = Depends(get_current_user), db: Session = Depends(get_db)
):
    updated = (
        db.query(Notification)
        .filter(
            Notification.recipient_id == user.id,
            Notification.read.is_(False),
        )
        .update({Notification.read: True}, synchronize_session=False)
    )
    db.commit()
    return ok({"updated": int(updated)})


def _load_owned(db: Session, notification_id: str, user: Employee) -> Notification:
    n = (
        db.query(Notification)
        .filter(Notification.id == notification_id)
        .one_or_none()
    )
    if n is None:
        raise ApiError(404, "Notification not found")
    if str(n.recipient_id) != str(user.id):
        raise ApiError(403, "Not your notification")
    return n


@router.patch("/{notification_id}")
def patch_notification(
    notification_id: str,
    body: MarkReadBody | None = None,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = _load_owned(db, notification_id, user)
    n.read = body.read if body is not None else True
    db.commit()
    db.refresh(n)
    return ok(_serialize(n))


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: str,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Alias for PATCH /{id} that marks a single notification read."""
    n = _load_owned(db, notification_id, user)
    n.read = True
    db.commit()
    db.refresh(n)
    return ok(_serialize(n))
