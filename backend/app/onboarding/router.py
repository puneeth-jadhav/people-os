from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, require_role
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

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])


class TemplateCreate(CamelModel):
    name: str
    role_target: str = "employee"
    department_id: str | None = None
    employment_type: str = "full_time"
    steps: list[dict] = []
    active: bool = True


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_task(t: OnboardingTask) -> dict:
    delayed = (
        t.deadline_at is not None
        and t.status != "done"
        and t.deadline_at < _now()
    )
    return {
        "id": str(t.id),
        "runId": str(t.run_id),
        "stepIndex": t.step_index,
        "title": t.title,
        "ownerId": str(t.owner_id) if t.owner_id else None,
        "status": t.status,
        "deadlineAt": t.deadline_at.isoformat() if t.deadline_at else None,
        "completedAt": t.completed_at.isoformat() if t.completed_at else None,
        "delayed": bool(delayed),
    }


def _progress(tasks: list[OnboardingTask]) -> dict:
    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == "done")
    percent = round((completed / total) * 100) if total else 0
    return {"completed": completed, "total": total, "percent": percent}


def _run_tasks(db: Session, run_id) -> list[OnboardingTask]:
    return (
        db.query(OnboardingTask)
        .filter(OnboardingTask.run_id == run_id)
        .order_by(OnboardingTask.step_index.asc())
        .all()
    )


def _employee_name(db: Session, emp_id) -> str:
    row = db.query(Employee.name).filter(Employee.id == emp_id).one_or_none()
    return row[0] if row and row[0] else "Employee"


@router.get("/mine")
def my_onboarding(
    user: Employee = Depends(get_current_user), db: Session = Depends(get_db)
):
    run = (
        db.query(OnboardingRun)
        .filter(OnboardingRun.employee_id == user.id)
        .one_or_none()
    )
    if run is None:
        return ok({"run": None})
    tasks = _run_tasks(db, run.id)
    return ok(
        {
            "run": {
                "id": str(run.id),
                "status": run.status,
                "startedAt": run.started_at.isoformat() if run.started_at else None,
                "completedAt": run.completed_at.isoformat()
                if run.completed_at
                else None,
                "employeeName": _employee_name(db, run.employee_id),
                "tasks": [_serialize_task(t) for t in tasks],
                "progress": _progress(tasks),
            }
        }
    )


@router.get("/runs")
def list_runs(
    user: Employee = Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    q = db.query(OnboardingRun).filter(OnboardingRun.status == "in_progress")
    if user.role != "hr_admin":
        report_ids = [
            row[0]
            for row in db.query(Employee.id)
            .filter(Employee.manager_id == user.id)
            .all()
        ]
        if not report_ids:
            return ok([])
        q = q.filter(OnboardingRun.employee_id.in_(report_ids))
    runs = q.order_by(OnboardingRun.started_at.asc()).all()
    result = []
    for run in runs:
        tasks = _run_tasks(db, run.id)
        result.append(
            {
                "id": str(run.id),
                "employeeId": str(run.employee_id),
                "employeeName": _employee_name(db, run.employee_id),
                "status": run.status,
                "startedAt": run.started_at.isoformat() if run.started_at else None,
                "progress": _progress(tasks),
                "tasks": [_serialize_task(t) for t in tasks],
            }
        )
    return ok(result)


@router.get("/tasks")
def list_tasks(
    user: Employee = Depends(get_current_user), db: Session = Depends(get_db)
):
    rows = (
        db.query(OnboardingTask, OnboardingRun)
        .join(OnboardingRun, OnboardingRun.id == OnboardingTask.run_id)
        .filter(
            OnboardingTask.owner_id == user.id,
            OnboardingTask.status != "done",
        )
        .order_by(OnboardingTask.deadline_at.asc())
        .all()
    )
    result = []
    for task, run in rows:
        item = _serialize_task(task)
        item["employeeId"] = str(run.employee_id)
        item["employeeName"] = _employee_name(db, run.employee_id)
        item["runStatus"] = run.status
        result.append(item)
    return ok(result)


@router.post("/runs/{run_id}/tasks/{task_id}/complete")
def complete_task(
    run_id: str,
    task_id: str,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = (
        db.query(OnboardingTask)
        .filter(OnboardingTask.id == task_id)
        .one_or_none()
    )
    if task is None or str(task.run_id) != str(run_id):
        raise ApiError(404, "Task not found for this run")
    if str(task.owner_id) != str(user.id):
        raise ApiError(403, "You do not own this task")
    if task.status == "locked":
        raise ApiError(409, "Task is locked and cannot be completed yet")
    if task.status == "done":
        raise ApiError(409, "Task already completed")

    run = (
        db.query(OnboardingRun).filter(OnboardingRun.id == run_id).one_or_none()
    )
    if run is None:
        raise ApiError(404, "Onboarding run not found")

    now = _now()
    task.status = "done"
    task.completed_at = now

    next_task = (
        db.query(OnboardingTask)
        .filter(
            OnboardingTask.run_id == run_id,
            OnboardingTask.step_index == task.step_index + 1,
        )
        .one_or_none()
    )
    next_task_id = None
    run_completed = False
    if next_task is not None:
        next_task_id = str(next_task.id)
        if next_task.status == "locked":
            next_task.status = "unlocked"
            notify(
                db,
                recipient_id=next_task.owner_id,
                type="onboarding.task_assigned",
                title=f"Your onboarding task is ready: {next_task.title}",
                link="/onboarding",
                resource_type="onboarding_task",
                resource_id=next_task.id,
                commit=False,
            )
    else:
        run.status = "completed"
        run.completed_at = now
        run_completed = True
        emp = (
            db.query(Employee)
            .filter(Employee.id == run.employee_id)
            .one_or_none()
        )
        if emp is not None and emp.status == "onboarding":
            emp.status = "active"

    audit(
        db,
        actor_id=user.id,
        action="onboarding.task_completed",
        resource_type="onboarding_task",
        resource_id=task.id,
        metadata={
            "runId": str(run_id),
            "stepIndex": task.step_index,
            "runCompleted": run_completed,
        },
        commit=False,
    )
    db.commit()
    db.refresh(task)

    emit(
        "onboarding.task_completed",
        {
            "runId": str(run_id),
            "taskId": str(task.id),
            "nextTaskId": next_task_id,
            "runCompleted": run_completed,
        },
        db,
    )

    result = _serialize_task(task)
    result["nextTaskId"] = next_task_id
    result["runCompleted"] = run_completed
    return ok(result)


@router.get("/templates")
def list_templates(
    user: Employee = Depends(require_role("hr_admin")),
    db: Session = Depends(get_db),
):
    rows = db.query(OnboardingTemplate).order_by(OnboardingTemplate.name.asc()).all()
    return ok(
        [
            {
                "id": str(t.id),
                "name": t.name,
                "roleTarget": t.role_target,
                "departmentId": str(t.department_id) if t.department_id else None,
                "employmentType": t.employment_type,
                "steps": t.steps or [],
                "active": bool(t.active),
            }
            for t in rows
        ]
    )


@router.post("/templates")
def create_template(
    body: TemplateCreate,
    user: Employee = Depends(require_role("hr_admin")),
    db: Session = Depends(get_db),
):
    tmpl = OnboardingTemplate(
        name=body.name,
        role_target=body.role_target,
        department_id=body.department_id,
        employment_type=body.employment_type,
        steps=body.steps,
        active=body.active,
    )
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return ok(
        {
            "id": str(tmpl.id),
            "name": tmpl.name,
            "roleTarget": tmpl.role_target,
            "departmentId": str(tmpl.department_id) if tmpl.department_id else None,
            "employmentType": tmpl.employment_type,
            "steps": tmpl.steps or [],
            "active": bool(tmpl.active),
        }
    )
