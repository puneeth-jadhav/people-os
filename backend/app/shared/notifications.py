from sqlalchemy.orm import Session

from app.shared.models import Notification


def notify(
    db: Session,
    recipient_id,
    type: str,
    title: str,
    body: str = "",
    link: str | None = None,
    resource_type: str | None = None,
    resource_id=None,
    commit: bool = True,
) -> Notification:
    row = Notification(
        recipient_id=recipient_id,
        type=type,
        title=title,
        body=body,
        link=link,
        resource_type=resource_type,
        resource_id=resource_id,
        read=False,
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    return row
