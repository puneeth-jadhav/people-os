from sqlalchemy.orm import Session

from app.shared.models import AuditLog

_SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "token_hash",
    "secret",
    "authorization",
}


def _scrub(metadata: dict | None) -> dict | None:
    if not metadata:
        return metadata
    cleaned = {}
    for key, value in metadata.items():
        if key.lower() in _SENSITIVE_KEYS:
            continue
        cleaned[key] = value
    return cleaned


def audit(
    db: Session,
    actor_id,
    action: str,
    resource_type: str,
    resource_id=None,
    metadata: dict | None = None,
    commit: bool = True,
) -> AuditLog:
    row = AuditLog(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_=_scrub(metadata),
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    return row
