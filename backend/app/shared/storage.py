import os
from pathlib import Path

from app.core.config import settings

_LOCAL_STORAGE_DIR = Path("./_storage")

try:
    from supabase import create_client  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    create_client = None


def _client():
    if not settings.supabase_configured or create_client is None:
        return None
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def upload_file(path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload bytes to private storage. Returns the storage path/key."""
    client = _client()
    if client is None:
        # Local dev fallback
        target = _LOCAL_STORAGE_DIR / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return path
    client.storage.from_(settings.SUPABASE_BUCKET).upload(
        path,
        data,
        {"content-type": content_type, "upsert": "true"},
    )
    return path


def create_signed_url(path: str, expires_in: int = 60) -> str:
    """Create a short-lived signed URL for private access."""
    client = _client()
    if client is None:
        # Local dev fallback — a fake signed path, never a permanent public URL
        return f"/_storage/{path}?dev_signed=1&expires_in={expires_in}"
    res = client.storage.from_(settings.SUPABASE_BUCKET).create_signed_url(
        path, expires_in
    )
    if isinstance(res, dict):
        return res.get("signedURL") or res.get("signed_url") or ""
    return str(res)
