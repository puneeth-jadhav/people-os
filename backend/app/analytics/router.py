from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_role
from app.shared.models import Employee
from app.shared.responses import ok

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("")
def get_analytics(
    user: Employee = Depends(require_role("hr_admin")),
    db: Session = Depends(get_db),
):
    return ok({})
