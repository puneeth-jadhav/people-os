from typing import Callable

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_access_token
from app.shared.models import Employee
from app.shared.responses import ApiError

RANK = {"employee": 1, "manager": 2, "hr_admin": 3}


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Employee:
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        raise ApiError(401, "Missing or invalid Authorization header")
    token = auth.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        raise ApiError(401, "Invalid or expired token")
    employee = (
        db.query(Employee).filter(Employee.id == payload["sub"]).one_or_none()
    )
    if employee is None:
        raise ApiError(401, "User no longer exists")
    return employee


def require_role(min_role: str) -> Callable:
    min_rank = RANK[min_role]

    def _dep(user: Employee = Depends(get_current_user)) -> Employee:
        if RANK.get(user.role, 0) < min_rank:
            raise ApiError(403, "Insufficient permissions")
        return user

    return _dep


def in_manager_chain(db: Session, manager_id, employee_id) -> bool:
    """True if manager_id appears in employee_id's manager chain (upward)."""
    if manager_id is None or employee_id is None:
        return False
    seen = set()
    current = (
        db.query(Employee).filter(Employee.id == employee_id).one_or_none()
    )
    while current is not None and current.manager_id is not None:
        if current.manager_id in seen:
            break
        seen.add(current.manager_id)
        if str(current.manager_id) == str(manager_id):
            return True
        current = (
            db.query(Employee).filter(Employee.id == current.manager_id).one_or_none()
        )
    return False


def can_access_employee(db: Session, user: Employee, target_employee_id) -> bool:
    if str(user.id) == str(target_employee_id):
        return True
    if user.role == "hr_admin":
        return True
    return in_manager_chain(db, user.id, target_employee_id)
