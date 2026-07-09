"""Realistic demo seed data for PeopleOS.

Demo logins (all password 'Password123!'):
    hr@peopleos.dev        (hr_admin)
    manager1@peopleos.dev  (manager, Engineering)
    manager2@peopleos.dev  (manager, Sales)
    employee@peopleos.dev  (employee, reports to manager1)
    newhire@peopleos.dev   (employee, status=onboarding)
"""
import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.shared.models import (
    Department,
    Document,
    DocumentAcknowledgement,
    Employee,
    Expense,
    LeaveBalance,
    LeaveRequest,
    LeaveRule,
    Notification,
    OnboardingRun,
    OnboardingTask,
    OnboardingTemplate,
)

DEMO_PASSWORD = "Password123!"
CURRENT_YEAR = date.today().year


def _truncate(db):
    db.execute(
        text(
            "truncate table audit_logs, notifications, expenses, "
            "document_acknowledgements, documents, onboarding_tasks, "
            "onboarding_runs, onboarding_templates, leave_requests, "
            "leave_balances, leave_rules, refresh_tokens, employees, "
            "departments restart identity cascade"
        )
    )
    db.commit()


def _now():
    return datetime.now(timezone.utc)


def seed():
    random.seed(42)
    db = SessionLocal()
    try:
        _truncate(db)
        pw = hash_password(DEMO_PASSWORD)

        # Departments
        eng = Department(name="Engineering")
        sales = Department(name="Sales")
        hr = Department(name="HR")
        db.add_all([eng, sales, hr])
        db.flush()

        # HR admin
        hr_admin = Employee(
            name="Hannah Reyes",
            email="hr@peopleos.dev",
            password_hash=pw,
            role="hr_admin",
            department_id=hr.id,
            designation="Head of People",
            join_date=date(2019, 1, 15),
            status="active",
        )
        db.add(hr_admin)
        db.flush()

        # Managers
        manager1 = Employee(
            name="Marcus Chen",
            email="manager1@peopleos.dev",
            password_hash=pw,
            role="manager",
            department_id=eng.id,
            designation="Engineering Manager",
            join_date=date(2020, 3, 1),
            status="active",
        )
        manager2 = Employee(
            name="Maria Lopez",
            email="manager2@peopleos.dev",
            password_hash=pw,
            role="manager",
            department_id=sales.id,
            designation="Sales Manager",
            join_date=date(2020, 6, 12),
            status="active",
        )
        db.add_all([manager1, manager2])
        db.flush()

        eng.head_employee_id = manager1.id
        sales.head_employee_id = manager2.id
        hr.head_employee_id = hr_admin.id

        # 6 employees (4 under manager1, 2 under manager2)
        employees = []
        primary = Employee(
            name="Evan Employee",
            email="employee@peopleos.dev",
            password_hash=pw,
            role="employee",
            department_id=eng.id,
            manager_id=manager1.id,
            designation="Software Engineer",
            join_date=date(2021, 4, 5),
            status="active",
        )
        employees.append(primary)

        eng_names = ["Priya Sharma", "Diego Torres", "Aisha Khan"]
        for i, nm in enumerate(eng_names):
            employees.append(
                Employee(
                    name=nm,
                    email=f"eng{i + 1}@peopleos.dev",
                    password_hash=pw,
                    role="employee",
                    department_id=eng.id,
                    manager_id=manager1.id,
                    designation="Software Engineer",
                    join_date=date(2021, 6 + i, 10),
                    status="active",
                )
            )

        sales_names = ["Sam Rivera", "Nadia Petrov"]
        for i, nm in enumerate(sales_names):
            employees.append(
                Employee(
                    name=nm,
                    email=f"sales{i + 1}@peopleos.dev",
                    password_hash=pw,
                    role="employee",
                    department_id=sales.id,
                    manager_id=manager2.id,
                    designation="Account Executive",
                    join_date=date(2021, 8 + i, 3),
                    status="active",
                )
            )

        db.add_all(employees)
        db.flush()

        # New hire (onboarding)
        new_hire = Employee(
            name="Noah Newhire",
            email="newhire@peopleos.dev",
            password_hash=pw,
            role="employee",
            department_id=eng.id,
            manager_id=manager1.id,
            designation="Junior Engineer",
            join_date=date.today(),
            status="onboarding",
        )
        db.add(new_hire)
        db.flush()

        # Leave rules
        rules = [
            LeaveRule(leave_type="casual", annual_quota=12, accrual_per_month=1, carry_forward_max=5, active=True),
            LeaveRule(leave_type="sick", annual_quota=10, accrual_per_month=0, carry_forward_max=0, active=True),
            LeaveRule(leave_type="earned", annual_quota=15, accrual_per_month=1.25, carry_forward_max=10, active=True),
        ]
        db.add_all(rules)
        db.flush()

        active_employees = [hr_admin, manager1, manager2] + employees
        rule_quota = {"casual": 12, "sick": 10, "earned": 15}

        # Leave balances for every active employee
        for emp in active_employees:
            for lt, quota in rule_quota.items():
                db.add(
                    LeaveBalance(
                        employee_id=emp.id,
                        leave_type=lt,
                        year=CURRENT_YEAR,
                        total_days=quota,
                        used_days=random.choice([0, 1, 2, 3]),
                        pending_days=0,
                        carry_forward_days=random.choice([0, 0, 2]),
                    )
                )
        db.flush()

        # Anomaly Profile targets:
        #   Profile A -> primary (employee@) : heavy Mon/Fri WFH last 8 weeks
        #   Profile B -> employees[1] (eng1)  : >=3 one-day sick leaves last 60 days
        profile_a = primary
        profile_b = employees[1]

        # 6 months of leave + WFH history (mix approved/rejected)
        reasons = [
            "Family function",
            "Medical appointment",
            "Personal work",
            "Travel plans",
            "Not feeling well",
        ]
        today = date.today()
        for emp in employees:
            approver = manager1 if emp.manager_id == manager1.id else manager2
            for m in range(1, 7):
                base = today - timedelta(days=30 * m + random.randint(0, 10))
                # leave history
                lt = random.choice(["casual", "sick", "earned"])
                dur = random.choice([1, 1, 2, 3])
                end = base + timedelta(days=dur - 1)
                status = random.choice(["approved", "approved", "rejected"])
                db.add(
                    LeaveRequest(
                        employee_id=emp.id,
                        request_type="leave",
                        leave_type=lt,
                        start_date=base,
                        end_date=end,
                        days_requested=dur,
                        status=status,
                        approver_id=approver.id,
                        reason=random.choice(reasons),
                        decision_note="Reviewed" if status != "pending" else None,
                        applied_at=datetime.combine(
                            base - timedelta(days=3), datetime.min.time(), timezone.utc
                        ),
                        resolved_at=datetime.combine(
                            base - timedelta(days=1), datetime.min.time(), timezone.utc
                        ),
                    )
                )
                # wfh history
                wbase = today - timedelta(days=30 * m + random.randint(11, 20))
                wstatus = random.choice(["approved", "approved", "rejected"])
                db.add(
                    LeaveRequest(
                        employee_id=emp.id,
                        request_type="wfh",
                        leave_type=None,
                        start_date=wbase,
                        end_date=wbase,
                        days_requested=1,
                        status=wstatus,
                        approver_id=approver.id,
                        reason="Working from home",
                        decision_note="Reviewed",
                        applied_at=datetime.combine(
                            wbase - timedelta(days=2), datetime.min.time(), timezone.utc
                        ),
                        resolved_at=datetime.combine(
                            wbase - timedelta(days=1), datetime.min.time(), timezone.utc
                        ),
                    )
                )

        # Anomaly Profile A: >=60% Mon/Fri WFH in last 8 weeks
        # Create 10 WFH approved requests, 8 of them on Monday/Friday.
        mon_fri_days = []
        d = today - timedelta(days=1)
        while len(mon_fri_days) < 8:
            if d.weekday() in (0, 4):  # Mon or Fri
                mon_fri_days.append(d)
            d -= timedelta(days=1)
            if (today - d).days > 56:
                break
        other_days = []
        d = today - timedelta(days=2)
        while len(other_days) < 2:
            if d.weekday() in (1, 2, 3):
                other_days.append(d)
            d -= timedelta(days=1)
            if (today - d).days > 56:
                break
        for wd in mon_fri_days + other_days:
            db.add(
                LeaveRequest(
                    employee_id=profile_a.id,
                    request_type="wfh",
                    leave_type=None,
                    start_date=wd,
                    end_date=wd,
                    days_requested=1,
                    status="approved",
                    approver_id=manager1.id,
                    reason="Working from home",
                    decision_note="Approved",
                    applied_at=datetime.combine(
                        wd - timedelta(days=2), datetime.min.time(), timezone.utc
                    ),
                    resolved_at=datetime.combine(
                        wd - timedelta(days=1), datetime.min.time(), timezone.utc
                    ),
                )
            )

        # Anomaly Profile B: >=3 one-day sick leaves in last 60 days
        for offset in (10, 25, 45):
            sd = today - timedelta(days=offset)
            db.add(
                LeaveRequest(
                    employee_id=profile_b.id,
                    request_type="leave",
                    leave_type="sick",
                    start_date=sd,
                    end_date=sd,
                    days_requested=1,
                    status="approved",
                    approver_id=manager1.id,
                    reason="Not feeling well",
                    decision_note="Approved",
                    applied_at=datetime.combine(
                        sd - timedelta(days=1), datetime.min.time(), timezone.utc
                    ),
                    resolved_at=datetime.combine(
                        sd, datetime.min.time(), timezone.utc
                    ),
                )
            )

        # Pending leave + WFH requests routed to correct manager
        for emp in employees[:3]:
            approver = manager1 if emp.manager_id == manager1.id else manager2
            fut = today + timedelta(days=random.randint(5, 20))
            db.add(
                LeaveRequest(
                    employee_id=emp.id,
                    request_type="leave",
                    leave_type="casual",
                    start_date=fut,
                    end_date=fut + timedelta(days=1),
                    days_requested=2,
                    status="pending",
                    approver_id=approver.id,
                    reason="Short vacation",
                    applied_at=_now(),
                )
            )
            db.add(
                LeaveRequest(
                    employee_id=emp.id,
                    request_type="wfh",
                    leave_type=None,
                    start_date=today + timedelta(days=3),
                    end_date=today + timedelta(days=3),
                    days_requested=1,
                    status="pending",
                    approver_id=approver.id,
                    reason="Working from home",
                    applied_at=_now(),
                )
            )

        db.flush()

        # Onboarding template + run + tasks for new hire
        template = OnboardingTemplate(
            name="Engineering New Hire",
            role_target="employee",
            department_id=eng.id,
            employment_type="full_time",
            steps=[
                {"index": 0, "title": "Sign offer & upload documents", "owner": "employee"},
                {"index": 1, "title": "Provision laptop & accounts", "owner": "manager"},
                {"index": 2, "title": "Complete HR orientation", "owner": "hr"},
                {"index": 3, "title": "Team intro & first task", "owner": "manager"},
            ],
            active=True,
        )
        db.add(template)
        db.flush()

        run = OnboardingRun(
            employee_id=new_hire.id,
            template_id=template.id,
            status="in_progress",
        )
        db.add(run)
        db.flush()

        owners = {
            "employee": new_hire.id,
            "manager": manager1.id,
            "hr": hr_admin.id,
        }
        statuses = ["done", "in_progress", "locked", "locked"]
        for step in template.steps:
            idx = step["index"]
            db.add(
                OnboardingTask(
                    run_id=run.id,
                    step_index=idx,
                    title=step["title"],
                    owner_id=owners[step["owner"]],
                    status=statuses[idx],
                    deadline_at=_now() + timedelta(days=idx + 2),
                    completed_at=_now() if statuses[idx] == "done" else None,
                )
            )
        db.flush()

        # Expenses (below and above 10000 threshold; various statuses)
        expense_rows = [
            (primary.id, 3200, "Travel", "Client visit cab fares", "pending_manager", manager1.id, None),
            (primary.id, 15000, "Equipment", "Standing desk", "pending_finance", manager1.id, None),
            (employees[1].id, 800, "Meals", "Team lunch", "paid", manager1.id, hr_admin.id),
            (employees[2].id, 24000, "Travel", "Conference flights", "pending_finance", manager1.id, None),
            (employees[4].id, 4500, "Software", "Design tool license", "rejected", manager2.id, None),
            (employees[5].id, 9999, "Meals", "Client dinner", "paid", manager2.id, hr_admin.id),
        ]
        for emp_id, amt, cat, desc, status, appr, fin in expense_rows:
            db.add(
                Expense(
                    employee_id=emp_id,
                    amount=amt,
                    category=cat,
                    description=desc,
                    expense_date=today - timedelta(days=random.randint(2, 40)),
                    receipt_path=None,
                    status=status,
                    approver_id=appr,
                    finance_approver_id=fin,
                    submitted_at=_now(),
                    resolved_at=_now() if status in ("paid", "rejected") else None,
                )
            )
        db.flush()

        # Documents
        payslip = Document(
            owner_id=primary.id,
            doc_category="personal",
            doc_type="payslip",
            title=f"Payslip {CURRENT_YEAR}-{today.month:02d} - Evan Employee",
            version=1,
            storage_path=f"personal/{primary.id}/payslip.pdf",
            content_text="Net pay salary earnings deductions tax",
            visible_roles=None,
            requires_ack=False,
            uploaded_by=hr_admin.id,
        )
        handbook = Document(
            owner_id=None,
            doc_category="policy",
            doc_type="handbook",
            title="Company Handbook",
            version=1,
            storage_path="policy/company-handbook.pdf",
            content_text="Welcome to the company culture values conduct policies benefits",
            visible_roles=["employee", "manager", "hr_admin"],
            requires_ack=False,
            uploaded_by=hr_admin.id,
        )
        leave_policy_v2 = Document(
            owner_id=None,
            doc_category="policy",
            doc_type="leave_policy",
            title="Leave Policy",
            version=2,
            change_summary="Updated carry-forward limits and added WFH guidance",
            storage_path="policy/leave-policy-v2.pdf",
            content_text="Leave policy carry forward casual sick earned work from home",
            visible_roles=["employee", "manager", "hr_admin"],
            requires_ack=False,
            uploaded_by=hr_admin.id,
        )
        security_policy = Document(
            owner_id=None,
            doc_category="policy",
            doc_type="security_policy",
            title="Information Security Policy",
            version=1,
            storage_path="policy/security-policy.pdf",
            content_text="Security data protection passwords confidentiality acceptable use",
            visible_roles=["employee", "manager", "hr_admin"],
            requires_ack=True,
            uploaded_by=hr_admin.id,
        )
        db.add_all([payslip, handbook, leave_policy_v2, security_policy])
        db.flush()

        # One acknowledgement so the ack-tracking demo has data
        db.add(
            DocumentAcknowledgement(
                document_id=security_policy.id,
                employee_id=manager1.id,
            )
        )

        # A couple of notifications
        db.add(
            Notification(
                recipient_id=manager1.id,
                type="request.submitted",
                title="New leave request",
                body="Evan Employee submitted a leave request awaiting your approval.",
                link="/requests",
                resource_type="leave_request",
                read=False,
            )
        )
        db.add(
            Notification(
                recipient_id=primary.id,
                type="policy.published",
                title="Please acknowledge: Information Security Policy",
                body="A policy requires your acknowledgement.",
                link="/documents",
                resource_type="document",
                resource_id=security_policy.id,
                read=False,
            )
        )

        db.commit()

        print("\n=== PeopleOS seed complete ===")
        print("Demo logins (password for all: %s):" % DEMO_PASSWORD)
        print("  hr@peopleos.dev        (hr_admin)")
        print("  manager1@peopleos.dev  (manager, Engineering)")
        print("  manager2@peopleos.dev  (manager, Sales)")
        print("  employee@peopleos.dev  (employee -> manager1)")
        print("  newhire@peopleos.dev   (employee, onboarding)")
        print("Anomaly demo profiles:")
        print("  Profile A (Mon/Fri WFH): employee@peopleos.dev")
        print("  Profile B (repeat sick): eng1@peopleos.dev")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
