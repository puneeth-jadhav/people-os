import re
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import can_access_employee, get_current_user, require_role
from app.core.security import hash_password
from app.events.dispatcher import emit
from app.shared.audit import audit
from app.shared.models import (
    Employee,
    OnboardingRun,
    OnboardingTask,
    OnboardingTemplate,
)
from app.shared.notifications import notify
from app.shared.responses import ApiError, CamelModel, ok

router = APIRouter(prefix="/api/v1/employees", tags=["employees"])

DEFAULT_PASSWORD = "Welcome@123"


class EmployeeCreate(CamelModel):
    name: str
    email: str
    role: str = "employee"
    department_id: str | None = None
    manager_id: str | None = None
    designation: str | None = None
    join_date: date | None = None
    employment_type: str = "full_time"


class IdNumbersUpdate(CamelModel):
    aadhaar_number: str | None = None
    pan_number: str | None = None


def _serialize_employee(e: Employee) -> dict:
    return {
        "id": str(e.id),
        "name": e.name,
        "email": e.email,
        "role": e.role,
        "departmentId": str(e.department_id) if e.department_id else None,
        "managerId": str(e.manager_id) if e.manager_id else None,
        "designation": e.designation,
        "status": e.status,
        "employmentType": e.employment_type,
        "joinDate": e.join_date.isoformat() if e.join_date else None,
    }


def _match_template(
    db: Session, role: str, department_id, employment_type: str
) -> OnboardingTemplate | None:
    """Find the best active template: exact → role+employment → role → any."""
    base = db.query(OnboardingTemplate).filter(OnboardingTemplate.active.is_(True))
    # 1. exact
    if department_id is not None:
        tmpl = base.filter(
            OnboardingTemplate.role_target == role,
            OnboardingTemplate.department_id == department_id,
            OnboardingTemplate.employment_type == employment_type,
        ).first()
        if tmpl:
            return tmpl
    # 2. role + employment_type
    tmpl = base.filter(
        OnboardingTemplate.role_target == role,
        OnboardingTemplate.employment_type == employment_type,
    ).first()
    if tmpl:
        return tmpl
    # 3. role only
    tmpl = base.filter(OnboardingTemplate.role_target == role).first()
    if tmpl:
        return tmpl
    # 4. any active
    return base.first()


@router.post("")
@router.post("/")
def create_employee(
    body: EmployeeCreate,
    user: Employee = Depends(require_role("hr_admin")),
    db: Session = Depends(get_db),
):
    if body.role not in ("employee", "manager", "hr_admin"):
        raise ApiError(422, "role must be employee, manager or hr_admin")

    existing = (
        db.query(Employee).filter(Employee.email == body.email).one_or_none()
    )
    if existing is not None:
        raise ApiError(409, "An employee with this email already exists")

    emp = Employee(
        name=body.name,
        email=body.email,
        password_hash=hash_password(DEFAULT_PASSWORD),
        role=body.role,
        department_id=body.department_id,
        manager_id=body.manager_id,
        designation=body.designation,
        join_date=body.join_date or date.today(),
        status="onboarding",
        employment_type=body.employment_type,
    )
    db.add(emp)
    db.flush()

    template = _match_template(
        db, body.role, body.department_id, body.employment_type
    )
    if template is None:
        raise ApiError(409, "No onboarding template available")

    run = OnboardingRun(
        employee_id=emp.id,
        template_id=template.id,
        status="in_progress",
    )
    db.add(run)
    db.flush()

    now = datetime.now(timezone.utc)
    steps = sorted(template.steps or [], key=lambda s: s.get("index", 0))
    tasks: list[OnboardingTask] = []
    for pos, step in enumerate(steps):
        idx = step.get("index", pos)
        owner_key = step.get("owner", "hr")
        if owner_key == "employee":
            owner_id = emp.id
        elif owner_key == "manager":
            owner_id = emp.manager_id or user.id
        else:  # 'hr' / 'hr_admin' / anything else
            owner_id = user.id
        deadline_days = step.get("deadlineDays")
        if deadline_days is None:
            deadline_days = idx + 1
        task = OnboardingTask(
            run_id=run.id,
            step_index=idx,
            title=step.get("title", f"Step {idx}"),
            owner_id=owner_id,
            status="unlocked" if pos == 0 else "locked",
            deadline_at=now + timedelta(days=int(deadline_days)),
        )
        db.add(task)
        tasks.append(task)
    db.flush()

    # Notify each distinct task owner
    notified_owners: set = set()
    for task in tasks:
        if task.owner_id in notified_owners:
            continue
        notified_owners.add(task.owner_id)
        notify(
            db,
            recipient_id=task.owner_id,
            type="onboarding.task_assigned",
            title=f"You have an onboarding task: {task.title}",
            link="/onboarding",
            resource_type="onboarding_task",
            resource_id=task.id,
            commit=False,
        )

    notify(
        db,
        recipient_id=emp.id,
        type="onboarding.started",
        title="Welcome! Your onboarding has started",
        link="/onboarding",
        resource_type="onboarding_run",
        resource_id=run.id,
        commit=False,
    )

    audit(
        db,
        actor_id=user.id,
        action="employee.created",
        resource_type="employee",
        resource_id=emp.id,
        metadata={"role": emp.role, "hasOnboarding": True},
        commit=False,
    )
    db.commit()
    db.refresh(emp)
    db.refresh(run)

    emit(
        "employee.created",
        {
            "employeeId": str(emp.id),
            "onboardingRunId": str(run.id),
            "role": emp.role,
        },
        db,
    )

    result = _serialize_employee(emp)
    result["onboardingRunId"] = str(run.id)
    result["taskCount"] = len(tasks)
    return ok(result)


@router.get("")
def list_employees(
    user: Employee = Depends(require_role("hr_admin")),
    db: Session = Depends(get_db),
):
    rows = db.query(Employee).order_by(Employee.name.asc()).all()
    return ok([_serialize_employee(e) for e in rows])


@router.patch("/me/id-numbers")
def update_my_id_numbers(
    body: IdNumbersUpdate,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    emp = db.query(Employee).filter(Employee.id == user.id).one_or_none()
    if emp is None:
        raise ApiError(404, "Employee not found")

    updated: dict = {}

    if body.aadhaar_number is not None:
        digits = re.sub(r"\D", "", body.aadhaar_number)
        if len(digits) != 12:
            raise ApiError(422, "Aadhaar number must be exactly 12 digits")
        emp.aadhaar_number = digits
        updated["aadhaar"] = True

    if body.pan_number is not None:
        pan = body.pan_number.strip().upper()
        if not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", pan):
            raise ApiError(422, "PAN must match format ABCDE1234F")
        emp.pan_number = pan
        updated["pan"] = True

    db.commit()
    db.refresh(emp)

    audit(
        db,
        actor_id=user.id,
        action="employee.id_updated",
        resource_type="employee",
        resource_id=user.id,
        metadata=updated,
        commit=True,
    )

    return ok({
        "id": str(emp.id),
        "aadhaarNumber": emp.aadhaar_number,
        "panNumber": emp.pan_number,
    })



@router.get("/{employee_id}")
def get_employee(
    employee_id: str,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not can_access_employee(db, user, employee_id):
        raise ApiError(403, "Not allowed to view this employee")
    emp = db.query(Employee).filter(Employee.id == employee_id).one_or_none()
    if emp is None:
        raise ApiError(404, "Employee not found")
    return ok(_serialize_employee(emp))
