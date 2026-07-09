from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import can_access_employee, get_current_user
from app.shared.models import Employee, LeaveBalance, LeaveRequest
from app.shared.responses import ApiError, ok

router = APIRouter(prefix="/api/v1/requests", tags=["requests_history"])


def _serialize_request(r: LeaveRequest) -> dict:
    return {
        "id": str(r.id),
        "requestType": r.request_type,
        "leaveType": r.leave_type,
        "startDate": r.start_date.isoformat() if r.start_date else None,
        "endDate": r.end_date.isoformat() if r.end_date else None,
        "days": float(r.days_requested) if r.days_requested is not None else None,
        "status": r.status,
        "reason": r.reason,
    }


def _serialize_balance(b: LeaveBalance) -> dict:
    total = float(b.total_days or 0) + float(b.carry_forward_days or 0)
    used = float(b.used_days or 0)
    pending = float(b.pending_days or 0)
    return {
        "leaveType": b.leave_type,
        "total": total,
        "used": used,
        "pending": pending,
        "remaining": total - used - pending,
    }


def _anomaly_flags(requests: list[LeaveRequest]) -> list[str]:
    """Simple, explainable anomaly heuristics — no ML."""
    flags: list[str] = []
    today = date.today()

    # Rule 1: WFH clustering on Mon/Fri within last 8 weeks.
    wfh_cutoff = today - timedelta(weeks=8)
    wfh_days = 0
    monfri = 0
    for r in requests:
        if (
            r.request_type == "wfh"
            and r.status == "approved"
            and r.start_date is not None
            and r.start_date >= wfh_cutoff
        ):
            # Count each requested day; iterate day range.
            cur = r.start_date
            end = r.end_date or r.start_date
            while cur <= end:
                wfh_days += 1
                if cur.weekday() in (0, 4):
                    monfri += 1
                cur += timedelta(days=1)
    if wfh_days >= 5 and (monfri / wfh_days) >= 0.6:
        flags.append("WFH clusters on Mon/Fri")

    # Rule 2: frequent short sick leaves within last 60 days.
    sick_cutoff = today - timedelta(days=60)
    short_sick = 0
    for r in requests:
        if (
            r.request_type == "leave"
            and r.status == "approved"
            and (r.leave_type or "").lower() == "sick"
            and r.days_requested is not None
            and float(r.days_requested) == 1
            and r.start_date is not None
            and r.start_date >= sick_cutoff
        ):
            short_sick += 1
    if short_sick >= 3:
        flags.append("Frequent short sick leaves")

    return flags


def _team_overlap(
    db: Session, target: Employee, start: date, end: date
) -> list[dict]:
    """Other employees under the SAME manager whose approved/pending
    requests overlap [start, end]."""
    if target.manager_id is None:
        return []
    rows = (
        db.query(LeaveRequest, Employee.name)
        .join(Employee, Employee.id == LeaveRequest.employee_id)
        .filter(
            Employee.manager_id == target.manager_id,
            LeaveRequest.employee_id != target.id,
            LeaveRequest.status.in_(("pending", "approved")),
            LeaveRequest.start_date <= end,
            LeaveRequest.end_date >= start,
        )
        .order_by(LeaveRequest.start_date.asc())
        .all()
    )
    return [
        {
            "employeeName": name or "Colleague",
            "startDate": r.start_date.isoformat() if r.start_date else None,
            "endDate": r.end_date.isoformat() if r.end_date else None,
            "requestType": r.request_type,
        }
        for (r, name) in rows
    ]


@router.get("/history/{employee_id}")
def request_history(
    employee_id: str,
    months: int = Query(6, ge=1, le=36),
    overlap_start: date | None = Query(None, alias="overlapStart"),
    overlap_end: date | None = Query(None, alias="overlapEnd"),
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = (
        db.query(Employee).filter(Employee.id == employee_id).one_or_none()
    )
    if target is None:
        raise ApiError(404, "Employee not found")
    if not can_access_employee(db, user, target.id):
        raise ApiError(403, "You are not authorized to view this history")

    today = date.today()
    cutoff = today - timedelta(days=months * 31)

    requests = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.employee_id == target.id,
            LeaveRequest.start_date >= cutoff,
        )
        .order_by(LeaveRequest.start_date.desc())
        .all()
    )

    totals: dict[str, float] = {}
    for r in requests:
        if r.status != "approved":
            continue
        key = "wfh" if r.request_type == "wfh" else (r.leave_type or "leave")
        totals[key] = totals.get(key, 0.0) + float(r.days_requested or 0)

    year = today.year
    balances = (
        db.query(LeaveBalance)
        .filter(
            LeaveBalance.employee_id == target.id,
            LeaveBalance.year == year,
        )
        .order_by(LeaveBalance.leave_type.asc())
        .all()
    )

    result = {
        "requests": [_serialize_request(r) for r in requests],
        "totalsByType": totals,
        "balance": [_serialize_balance(b) for b in balances],
        "anomalyFlags": _anomaly_flags(requests),
    }

    if overlap_start is not None and overlap_end is not None:
        result["teamOverlap"] = _team_overlap(
            db, target, overlap_start, overlap_end
        )
    else:
        result["teamOverlap"] = []

    return ok(result)
