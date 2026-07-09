from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    revoke_refresh_token,
    verify_password,
    verify_refresh_token,
)
from app.shared.models import Employee
from app.shared.responses import ApiError, CamelModel, ok

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(CamelModel):
    email: str
    password: str


class RefreshRequest(CamelModel):
    refresh_token: str


class LogoutRequest(CamelModel):
    refresh_token: str


def _access_for(user: Employee) -> str:
    return create_access_token(sub=str(user.id), role=user.role, name=user.name or "")


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(Employee).filter(Employee.email == body.email).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash or ""):
        raise ApiError(401, "Invalid email or password")
    access = _access_for(user)
    refresh = create_refresh_token(db, str(user.id))
    return ok(
        {
            "accessToken": access,
            "refreshToken": refresh,
            "user": {
                "id": str(user.id),
                "name": user.name,
                "email": str(user.email),
                "role": user.role,
            },
        }
    )


@router.post("/refresh")
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    row = verify_refresh_token(db, body.refresh_token)
    if row is None:
        raise ApiError(401, "Invalid or expired refresh token")
    user = db.query(Employee).filter(Employee.id == row.employee_id).one_or_none()
    if user is None:
        raise ApiError(401, "User no longer exists")
    access = _access_for(user)
    return ok({"accessToken": access})


@router.post("/logout")
def logout(body: LogoutRequest, db: Session = Depends(get_db)):
    revoke_refresh_token(db, body.refresh_token)
    return ok({"loggedOut": True})


@router.get("/me")
def me(user: Employee = Depends(get_current_user)):
    return ok(
        {
            "id": str(user.id),
            "name": user.name,
            "email": str(user.email),
            "role": user.role,
            "departmentId": str(user.department_id) if user.department_id else None,
            "managerId": str(user.manager_id) if user.manager_id else None,
            "designation": user.designation,
            "status": user.status,
        }
    )
