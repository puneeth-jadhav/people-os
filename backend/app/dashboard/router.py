from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.shared.models import (
    Document,
    DocumentAcknowledgement,
    Employee,
    Expense,
    LeaveBalance,
    LeaveRequest,
    OnboardingRun,
    OnboardingTask,
)
from app.shared.responses import ok

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def _greeting(now: datetime) -> str:
    h = now.hour
    if h < 12:
        return "Good morning"
    if h < 17:
        return "Good afternoon"
    return "Good evening"


def _first_name(name: str | None) -> str:
    if not name:
        return "there"
    return name.strip().split(" ")[0]


def _age_days(ts) -> int:
    """Whole days since a timezone-aware/naive datetime."""
    if ts is None:
        return 0
    now = datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    delta = now - ts
    return max(0, delta.days)


def _prune(payload: dict) -> dict:
    """Drop empty zone arrays so the frontend can render 'all caught up'."""
    zone_keys = (
        "needsAttention",
        "waitingOnOthers",
        "upcoming",
        "recentChanges",
        "quickActions",
    )
    out = {}
    for k, v in payload.items():
        if k in zone_keys and isinstance(v, list) and len(v) == 0:
            continue
        out[k] = v
    return out


def _direct_report_ids(db: Session, manager: Employee) -> list:
    rows = (
        db.query(Employee.id)
        .filter(Employee.manager_id == manager.id)
        .all()
    )
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Employee dashboard
# ---------------------------------------------------------------------------
def _employee_dashboard(db: Session, user: Employee) -> dict:
    year = date.today().year
    today = date.today()

    # Leave balances (current year)
    balances = (
        db.query(LeaveBalance)
        .filter(
            LeaveBalance.employee_id == user.id,
            LeaveBalance.year == year,
        )
        .all()
    )
    balance_summary = []
    remaining_hint_parts = []
    for b in balances:
        total = float(b.total_days or 0) + float(b.carry_forward_days or 0)
        used = float(b.used_days or 0)
        pending = float(b.pending_days or 0)
        remaining = total - used - pending
        balance_summary.append(
            {
                "leaveType": b.leave_type,
                "total": total,
                "used": used,
                "pending": pending,
                "remaining": remaining,
            }
        )
        remaining_hint_parts.append(f"{remaining:g} {b.leave_type}")

    # Upcoming approved leave/wfh
    upcoming = []
    approved_upcoming = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.employee_id == user.id,
            LeaveRequest.status == "approved",
            LeaveRequest.end_date >= today,
        )
        .order_by(LeaveRequest.start_date.asc())
        .limit(5)
        .all()
    )
    for r in approved_upcoming:
        label = "WFH" if r.request_type == "wfh" else f"{(r.leave_type or 'leave').title()} leave"
        upcoming.append(
            {
                "id": str(r.id),
                "kind": r.request_type,
                "title": label,
                "subtitle": f"{r.start_date.isoformat()} → {r.end_date.isoformat()}",
                "link": "/requests",
                "startDate": r.start_date.isoformat(),
                "endDate": r.end_date.isoformat(),
            }
        )

    # Next payslip (latest personal payslip doc)
    payslip = (
        db.query(Document)
        .filter(
            Document.owner_id == user.id,
            Document.doc_type == "payslip",
        )
        .order_by(Document.created_at.desc())
        .first()
    )
    if payslip is not None:
        upcoming.append(
            {
                "id": str(payslip.id),
                "kind": "payslip",
                "title": "Latest payslip available",
                "subtitle": payslip.title,
                "link": "/documents",
            }
        )

    # Policy docs requiring ack not yet acked by this user
    acked_ids = {
        r[0]
        for r in db.query(DocumentAcknowledgement.document_id)
        .filter(DocumentAcknowledgement.employee_id == user.id)
        .all()
    }
    unacked = (
        db.query(Document)
        .filter(
            Document.doc_category == "policy",
            Document.requires_ack.is_(True),
        )
        .all()
    )
    needs_attention = []
    for d in unacked:
        if d.id in acked_ids:
            continue
        roles = d.visible_roles
        if roles and user.role not in roles:
            continue
        needs_attention.append(
            {
                "id": str(d.id),
                "kind": "policy_ack",
                "title": f"Acknowledge: {d.title}",
                "subtitle": f"Version {d.version} requires your acknowledgement",
                "link": "/documents",
            }
        )

    # Rejected items -> needsAttention
    rejected_leaves = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.employee_id == user.id,
            LeaveRequest.status == "rejected",
        )
        .order_by(LeaveRequest.resolved_at.desc().nullslast())
        .limit(3)
        .all()
    )
    for r in rejected_leaves:
        label = "WFH" if r.request_type == "wfh" else f"{(r.leave_type or 'leave').title()} leave"
        needs_attention.append(
            {
                "id": str(r.id),
                "kind": "rejected_leave",
                "title": f"{label} request was rejected",
                "subtitle": r.decision_note or "See details",
                "link": "/requests",
            }
        )
    rejected_expenses = (
        db.query(Expense)
        .filter(
            Expense.employee_id == user.id,
            Expense.status == "rejected",
        )
        .order_by(Expense.resolved_at.desc().nullslast())
        .limit(3)
        .all()
    )
    for e in rejected_expenses:
        needs_attention.append(
            {
                "id": str(e.id),
                "kind": "rejected_expense",
                "title": "Expense claim rejected",
                "subtitle": f"{e.category} — {float(e.amount):g}",
                "link": "/expenses",
            }
        )

    # waitingOnOthers: own pending leave + expenses
    waiting = []
    pending_leaves = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.employee_id == user.id,
            LeaveRequest.status == "pending",
        )
        .order_by(LeaveRequest.applied_at.asc())
        .all()
    )
    for r in pending_leaves:
        label = "WFH" if r.request_type == "wfh" else f"{(r.leave_type or 'leave').title()} leave"
        waiting.append(
            {
                "id": str(r.id),
                "kind": "pending_leave",
                "title": f"{label} awaiting approval",
                "subtitle": f"{r.start_date.isoformat()} → {r.end_date.isoformat()}",
                "link": "/requests",
                "ageDays": _age_days(r.applied_at),
            }
        )
    pending_expenses = (
        db.query(Expense)
        .filter(
            Expense.employee_id == user.id,
            Expense.status.in_(["submitted", "pending_manager", "pending_finance"]),
        )
        .order_by(Expense.submitted_at.asc())
        .all()
    )
    for e in pending_expenses:
        stage = {
            "pending_manager": "with your manager",
            "pending_finance": "with finance",
            "submitted": "submitted",
        }.get(e.status, e.status)
        waiting.append(
            {
                "id": str(e.id),
                "kind": "pending_expense",
                "title": f"Expense {stage}",
                "subtitle": f"{e.category} — {float(e.amount):g}",
                "link": "/expenses",
                "ageDays": _age_days(e.submitted_at),
            }
        )

    now = datetime.now(timezone.utc)
    hint = ", ".join(remaining_hint_parts) if remaining_hint_parts else "no balances on record"
    hero = {
        "greeting": f"{_greeting(now)}, {_first_name(user.name)}",
        "headline": "Here's your day at a glance",
        "subtext": f"Leave remaining: {hint}",
    }

    quick_actions = [
        {"label": "Apply for leave", "link": "/requests/new"},
        {"label": "Request WFH", "link": "/requests/new?type=wfh"},
        {"label": "Submit expense", "link": "/expenses/new"},
        {"label": "View documents", "link": "/documents"},
    ]

    return _prune(
        {
            "role": "employee",
            "experience": "employee",
            "hero": hero,
            "leaveBalances": balance_summary,
            "needsAttention": needs_attention,
            "waitingOnOthers": waiting,
            "upcoming": upcoming,
            "recentChanges": [],
            "quickActions": quick_actions,
        }
    )


# ---------------------------------------------------------------------------
# Manager dashboard
# ---------------------------------------------------------------------------
def _manager_context_hint(db: Session, employee_id, year: int) -> str:
    balances = (
        db.query(LeaveBalance)
        .filter(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.year == year,
        )
        .all()
    )
    parts = []
    for b in balances:
        total = float(b.total_days or 0) + float(b.carry_forward_days or 0)
        remaining = total - float(b.used_days or 0) - float(b.pending_days or 0)
        parts.append(f"{remaining:g} {b.leave_type[:2].upper()} left")
    wfh_used = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.request_type == "wfh",
            LeaveRequest.status == "approved",
        )
        .count()
    )
    parts.append(f"{wfh_used} WFH days used")
    return ", ".join(parts) if parts else "no history"


def _manager_dashboard(db: Session, user: Employee) -> dict:
    year = date.today().year
    today = date.today()
    report_ids = _direct_report_ids(db, user)

    needs_attention = []

    # Pending leave requests where user is approver
    pending_leaves = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.approver_id == user.id,
            LeaveRequest.status == "pending",
        )
        .order_by(LeaveRequest.applied_at.asc())
        .all()
    )
    emp_names = {
        e.id: e.name
        for e in db.query(Employee).filter(
            Employee.id.in_(report_ids or [user.id])
        ).all()
    }
    for r in pending_leaves:
        label = "WFH" if r.request_type == "wfh" else f"{(r.leave_type or 'leave').title()} leave"
        who = emp_names.get(r.employee_id) or "A team member"
        needs_attention.append(
            {
                "id": str(r.id),
                "kind": "approve_leave",
                "title": f"{who}: {label}",
                "subtitle": f"{r.start_date.isoformat()} → {r.end_date.isoformat()} ({float(r.days_requested):g}d)",
                "link": "/requests",
                "ageDays": _age_days(r.applied_at),
                "contextHint": _manager_context_hint(db, r.employee_id, year),
            }
        )

    # Pending expenses where user is approver (manager stage)
    pending_expenses = (
        db.query(Expense)
        .filter(
            Expense.approver_id == user.id,
            Expense.status == "pending_manager",
        )
        .order_by(Expense.submitted_at.asc())
        .all()
    )
    exp_emp_ids = [e.employee_id for e in pending_expenses]
    if exp_emp_ids:
        for e in db.query(Employee).filter(Employee.id.in_(exp_emp_ids)).all():
            emp_names[e.id] = e.name
    for e in pending_expenses:
        who = emp_names.get(e.employee_id) or "A team member"
        needs_attention.append(
            {
                "id": str(e.id),
                "kind": "approve_expense",
                "title": f"{who}: {e.category} expense",
                "subtitle": f"{float(e.amount):g} — {e.description or ''}".strip(),
                "link": "/expenses",
                "ageDays": _age_days(e.submitted_at),
            }
        )

    # Team availability: reports on approved leave/wfh today or upcoming
    team_availability = []
    if report_ids:
        avail_rows = (
            db.query(LeaveRequest)
            .filter(
                LeaveRequest.employee_id.in_(report_ids),
                LeaveRequest.status == "approved",
                LeaveRequest.end_date >= today,
            )
            .order_by(LeaveRequest.start_date.asc())
            .limit(15)
            .all()
        )
        avail_names = {
            e.id: e.name
            for e in db.query(Employee).filter(Employee.id.in_(report_ids)).all()
        }
        for r in avail_rows:
            is_today = r.start_date <= today <= r.end_date
            kind = "wfh" if r.request_type == "wfh" else "leave"
            team_availability.append(
                {
                    "id": str(r.id),
                    "employee": avail_names.get(r.employee_id, "Report"),
                    "kind": kind,
                    "status": "today" if is_today else "upcoming",
                    "startDate": r.start_date.isoformat(),
                    "endDate": r.end_date.isoformat(),
                }
            )

    # Onboarding delays for reports
    recent_changes = []
    now = datetime.now(timezone.utc)
    if report_ids:
        delayed = (
            db.query(OnboardingTask, OnboardingRun)
            .join(OnboardingRun, OnboardingTask.run_id == OnboardingRun.id)
            .filter(
                OnboardingRun.employee_id.in_(report_ids),
                OnboardingTask.status != "done",
                OnboardingTask.deadline_at < now,
            )
            .all()
        )
        for task, _run in delayed:
            needs_attention.append(
                {
                    "id": str(task.id),
                    "kind": "onboarding_delay",
                    "title": f"Onboarding overdue: {task.title}",
                    "subtitle": f"Deadline was {task.deadline_at.date().isoformat()}",
                    "link": "/onboarding",
                    "ageDays": _age_days(task.deadline_at),
                }
            )

    hero = {
        "greeting": f"{_greeting(now)}, {_first_name(user.name)}",
        "headline": "Your team needs you",
        "subtext": (
            f"{len(pending_leaves) + len(pending_expenses)} pending approval(s), "
            f"{len(team_availability)} team member(s) away soon"
        ),
    }

    quick_actions = [
        {"label": "Review approvals", "link": "/requests"},
        {"label": "Team calendar", "link": "/team"},
        {"label": "Review expenses", "link": "/expenses"},
    ]

    return _prune(
        {
            "role": "manager",
            "experience": "manager",
            "hero": hero,
            "needsAttention": needs_attention,
            "teamAvailability": team_availability,
            "waitingOnOthers": [],
            "upcoming": [],
            "recentChanges": recent_changes,
            "quickActions": quick_actions,
        }
    )


# ---------------------------------------------------------------------------
# New-hire dashboard
# ---------------------------------------------------------------------------
def _new_hire_dashboard(db: Session, user: Employee) -> dict:
    now = datetime.now(timezone.utc)
    run = (
        db.query(OnboardingRun)
        .filter(OnboardingRun.employee_id == user.id)
        .first()
    )

    hero = {
        "greeting": f"{_greeting(now)}, {_first_name(user.name)}",
        "headline": "Welcome aboard! Let's get you set up",
        "subtext": "Complete your onboarding steps to get started.",
    }

    if run is None:
        return _prune(
            {
                "role": user.role,
                "experience": "new_hire",
                "hero": hero,
                "onboarding": {"completed": 0, "total": 0, "percent": 0},
                "needsAttention": [],
                "waitingOnOthers": [],
                "upcoming": [],
                "recentChanges": [],
                "quickActions": [{"label": "View documents", "link": "/documents"}],
            }
        )

    tasks = (
        db.query(OnboardingTask)
        .filter(OnboardingTask.run_id == run.id)
        .order_by(OnboardingTask.step_index.asc())
        .all()
    )
    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == "done")
    percent = int(round((completed / total) * 100)) if total else 0

    # Current action = first unlocked / in_progress task owned by the new hire
    current_action = None
    waiting_on = None
    next_task = None
    for t in tasks:
        if t.status in ("unlocked", "in_progress"):
            if str(t.owner_id) == str(user.id):
                current_action = t
            else:
                waiting_on = t
            break

    # Next locked task after the current active one
    for t in tasks:
        if t.status == "locked":
            next_task = t
            break

    owner_ids = [t.owner_id for t in tasks if t.owner_id]
    owner_names = {}
    if owner_ids:
        owner_names = {
            e.id: e.name
            for e in db.query(Employee).filter(Employee.id.in_(owner_ids)).all()
        }

    needs_attention = []
    if current_action is not None:
        needs_attention.append(
            {
                "id": str(current_action.id),
                "kind": "onboarding_action",
                "title": current_action.title,
                "subtitle": "This is your next step — complete it to continue.",
                "link": "/onboarding",
                "deadline": current_action.deadline_at.date().isoformat()
                if current_action.deadline_at
                else None,
            }
        )

    waiting = []
    if waiting_on is not None:
        owner_name = owner_names.get(waiting_on.owner_id, "your team")
        waiting.append(
            {
                "id": str(waiting_on.id),
                "kind": "onboarding_wait",
                "title": waiting_on.title,
                "subtitle": f"Waiting on {owner_name}",
                "link": "/onboarding",
                "waitingOnName": owner_name,
                "ageDays": _age_days(run.started_at),
            }
        )

    upcoming = []
    if next_task is not None:
        upcoming.append(
            {
                "id": str(next_task.id),
                "kind": "onboarding_next",
                "title": f"Up next: {next_task.title}",
                "subtitle": "Unlocks after the current step",
                "link": "/onboarding",
            }
        )

    # Pending document requirements (policies requiring ack)
    acked_ids = {
        r[0]
        for r in db.query(DocumentAcknowledgement.document_id)
        .filter(DocumentAcknowledgement.employee_id == user.id)
        .all()
    }
    unacked = (
        db.query(Document)
        .filter(
            Document.doc_category == "policy",
            Document.requires_ack.is_(True),
        )
        .all()
    )
    for d in unacked:
        if d.id in acked_ids:
            continue
        roles = d.visible_roles
        if roles and user.role not in roles:
            continue
        needs_attention.append(
            {
                "id": str(d.id),
                "kind": "policy_ack",
                "title": f"Acknowledge: {d.title}",
                "subtitle": "Required as part of onboarding",
                "link": "/documents",
            }
        )

    return _prune(
        {
            "role": user.role,
            "experience": "new_hire",
            "hero": hero,
            "onboarding": {
                "completed": completed,
                "total": total,
                "percent": percent,
                "tasks": [
                    {
                        "id": str(t.id),
                        "title": t.title,
                        "status": t.status,
                        "owner": owner_names.get(t.owner_id, ""),
                        "isMine": str(t.owner_id) == str(user.id),
                    }
                    for t in tasks
                ],
            },
            "needsAttention": needs_attention,
            "waitingOnOthers": waiting,
            "upcoming": upcoming,
            "recentChanges": [],
            "quickActions": [
                {"label": "Upload documents", "link": "/documents"},
                {"label": "View onboarding", "link": "/onboarding"},
            ],
        }
    )


# ---------------------------------------------------------------------------
# HR admin dashboard
# ---------------------------------------------------------------------------
def _hr_dashboard(db: Session, user: Employee) -> dict:
    now = datetime.now(timezone.utc)
    today = date.today()

    # Active onboarding runs
    active_runs = (
        db.query(OnboardingRun)
        .filter(OnboardingRun.status == "in_progress")
        .all()
    )
    run_emp_ids = [r.employee_id for r in active_runs]
    emp_names = {}
    if run_emp_ids:
        emp_names = {
            e.id: e.name
            for e in db.query(Employee).filter(Employee.id.in_(run_emp_ids)).all()
        }
    onboarding_runs = []
    for r in active_runs:
        tasks = (
            db.query(OnboardingTask)
            .filter(OnboardingTask.run_id == r.id)
            .all()
        )
        total = len(tasks)
        done = sum(1 for t in tasks if t.status == "done")
        onboarding_runs.append(
            {
                "id": str(r.id),
                "employee": emp_names.get(r.employee_id, "New hire"),
                "completed": done,
                "total": total,
                "percent": int(round((done / total) * 100)) if total else 0,
                "startedAt": r.started_at.date().isoformat() if r.started_at else None,
            }
        )

    # Delayed onboarding tasks (past deadline, not done)
    delayed = (
        db.query(OnboardingTask, OnboardingRun)
        .join(OnboardingRun, OnboardingTask.run_id == OnboardingRun.id)
        .filter(
            OnboardingTask.status != "done",
            OnboardingTask.deadline_at < now,
        )
        .all()
    )
    delayed_emp_ids = list({run.employee_id for _t, run in delayed})
    if delayed_emp_ids:
        for e in db.query(Employee).filter(Employee.id.in_(delayed_emp_ids)).all():
            emp_names[e.id] = e.name
    needs_attention = []
    for task, run in delayed:
        needs_attention.append(
            {
                "id": str(task.id),
                "kind": "onboarding_delay",
                "title": f"Delayed: {task.title}",
                "subtitle": f"{emp_names.get(run.employee_id, 'New hire')} — due {task.deadline_at.date().isoformat()}",
                "link": "/onboarding",
                "ageDays": _age_days(task.deadline_at),
            }
        )

    # Finance queue: expenses pending_finance
    finance_queue = (
        db.query(Expense)
        .filter(Expense.status == "pending_finance")
        .order_by(Expense.submitted_at.asc())
        .all()
    )
    fin_emp_ids = [e.employee_id for e in finance_queue]
    if fin_emp_ids:
        for e in db.query(Employee).filter(Employee.id.in_(fin_emp_ids)).all():
            emp_names[e.id] = e.name
    finance_items = []
    for e in finance_queue:
        item = {
            "id": str(e.id),
            "kind": "finance_approval",
            "title": f"{emp_names.get(e.employee_id, 'Employee')}: {e.category}",
            "subtitle": f"{float(e.amount):g} — awaiting finance approval",
            "link": "/expenses",
            "amount": float(e.amount),
            "ageDays": _age_days(e.submitted_at),
        }
        finance_items.append(item)
        needs_attention.append(item)

    # Policy acknowledgement status
    active_headcount = (
        db.query(Employee)
        .filter(Employee.status == "active")
        .count()
    )
    ack_policies = (
        db.query(Document)
        .filter(
            Document.doc_category == "policy",
            Document.requires_ack.is_(True),
        )
        .all()
    )
    ack_status = []
    for d in ack_policies:
        acked = (
            db.query(DocumentAcknowledgement)
            .filter(DocumentAcknowledgement.document_id == d.id)
            .count()
        )
        ack_status.append(
            {
                "id": str(d.id),
                "title": d.title,
                "version": d.version,
                "acked": acked,
                "total": active_headcount,
                "percent": int(round((acked / active_headcount) * 100))
                if active_headcount
                else 0,
            }
        )

    # Leave anomalies (best-effort simple count; full SQL in Phase 7)
    sixty_days_ago = today.fromordinal(today.toordinal() - 60)
    frequent_sick = (
        db.query(LeaveRequest.employee_id)
        .filter(
            LeaveRequest.request_type == "leave",
            LeaveRequest.leave_type == "sick",
            LeaveRequest.days_requested == 1,
            LeaveRequest.start_date >= sixty_days_ago,
        )
        .all()
    )
    sick_counts = {}
    for (emp_id,) in frequent_sick:
        sick_counts[emp_id] = sick_counts.get(emp_id, 0) + 1
    anomaly_count = sum(1 for c in sick_counts.values() if c >= 3)

    recent_changes = []
    if anomaly_count:
        recent_changes.append(
            {
                "id": "anomaly-sick",
                "kind": "anomaly",
                "title": f"{anomaly_count} employee(s) with frequent single-day sick leave",
                "subtitle": "Flagged for review (last 60 days)",
                "link": "/requests",
            }
        )

    hero = {
        "greeting": f"{_greeting(now)}, {_first_name(user.name)}",
        "headline": "People operations overview",
        "subtext": (
            f"{len(active_runs)} active onboarding(s), "
            f"{len(finance_queue)} expense(s) in finance queue, "
            f"{len(delayed)} delayed task(s)"
        ),
    }

    quick_actions = [
        {"label": "Manage documents", "link": "/documents"},
        {"label": "Onboarding", "link": "/onboarding"},
        {"label": "Finance queue", "link": "/expenses"},
        {"label": "Audit log", "link": "/audit"},
    ]

    return _prune(
        {
            "role": "hr_admin",
            "experience": "hr_admin",
            "hero": hero,
            "onboardingRuns": onboarding_runs,
            "ackStatus": ack_status,
            "financeQueue": finance_items,
            "needsAttention": needs_attention,
            "waitingOnOthers": [],
            "upcoming": [],
            "recentChanges": recent_changes,
            "quickActions": quick_actions,
        }
    )


@router.get("")
def get_dashboard(
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.status == "onboarding":
        return ok(_new_hire_dashboard(db, user))
    if user.role == "hr_admin":
        return ok(_hr_dashboard(db, user))
    if user.role == "manager":
        return ok(_manager_dashboard(db, user))
    return ok(_employee_dashboard(db, user))
