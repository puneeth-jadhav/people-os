import uuid

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Column,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.dialects.postgresql import CITEXT

from app.core.db import Base


def pk_col():
    return Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Department(Base):
    __tablename__ = "departments"

    id = pk_col()
    name = Column(Text, unique=True, nullable=False)
    head_employee_id = Column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
    )


class Employee(Base):
    __tablename__ = "employees"

    id = pk_col()
    name = Column(Text)
    email = Column(CITEXT, unique=True, nullable=False)
    password_hash = Column(Text)
    role = Column(Text)
    department_id = Column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True
    )
    manager_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=True)
    designation = Column(Text)
    join_date = Column(Date)
    status = Column(Text, default="onboarding")
    employment_type = Column(Text, default="full_time")
    aadhaar_number = Column(Text)
    pan_number = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "role in ('employee','manager','hr_admin')", name="employees_role_check"
        ),
        CheckConstraint(
            "status in ('onboarding','active','terminated')",
            name="employees_status_check",
        ),
        Index("ix_employees_role", "role"),
        Index("ix_employees_manager_id", "manager_id"),
        Index("ix_employees_department_id", "department_id"),
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = pk_col()
    employee_id = Column(
        UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE")
    )
    token_hash = Column(Text, unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True))
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_refresh_tokens_employee_id", "employee_id"),)


class LeaveRule(Base):
    __tablename__ = "leave_rules"

    id = pk_col()
    leave_type = Column(Text)
    annual_quota = Column(Numeric)
    accrual_per_month = Column(Numeric, default=0)
    carry_forward_max = Column(Numeric, default=0)
    active = Column(Boolean, default=True)


class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    id = pk_col()
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"))
    leave_type = Column(Text)
    year = Column(Integer)
    total_days = Column(Numeric)
    used_days = Column(Numeric, default=0)
    pending_days = Column(Numeric, default=0)
    carry_forward_days = Column(Numeric, default=0)

    __table_args__ = (
        UniqueConstraint(
            "employee_id", "leave_type", "year", name="uq_leave_balances_emp_type_year"
        ),
        CheckConstraint("used_days >= 0", name="leave_balances_used_check"),
        CheckConstraint("pending_days >= 0", name="leave_balances_pending_check"),
    )


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = pk_col()
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"))
    request_type = Column(Text, default="leave")
    leave_type = Column(Text, nullable=True)
    start_date = Column(Date)
    end_date = Column(Date)
    days_requested = Column(Numeric)
    status = Column(Text, default="pending")
    approver_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=True)
    reason = Column(Text, nullable=True)
    decision_note = Column(Text, nullable=True)
    applied_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "request_type in ('leave','wfh')", name="leave_requests_type_check"
        ),
        CheckConstraint(
            "status in ('pending','approved','rejected','cancelled')",
            name="leave_requests_status_check",
        ),
        CheckConstraint("days_requested > 0", name="leave_requests_days_check"),
        CheckConstraint("end_date >= start_date", name="leave_requests_dates_check"),
        Index("ix_leave_requests_emp_status", "employee_id", "status"),
        Index("ix_leave_requests_approver_status", "approver_id", "status"),
        Index("ix_leave_requests_dates", "start_date", "end_date"),
        Index("ix_leave_requests_emp_applied", "employee_id", "applied_at"),
    )


class OnboardingTemplate(Base):
    __tablename__ = "onboarding_templates"

    id = pk_col()
    name = Column(Text)
    role_target = Column(Text)
    department_id = Column(UUID(as_uuid=True), nullable=True)
    employment_type = Column(Text)
    steps = Column(JSONB)
    active = Column(Boolean, default=True)


class OnboardingRun(Base):
    __tablename__ = "onboarding_runs"

    id = pk_col()
    employee_id = Column(
        UUID(as_uuid=True), ForeignKey("employees.id"), unique=True
    )
    template_id = Column(UUID(as_uuid=True), ForeignKey("onboarding_templates.id"))
    status = Column(Text, default="in_progress")
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status in ('in_progress','completed')", name="onboarding_runs_status_check"
        ),
    )


class OnboardingTask(Base):
    __tablename__ = "onboarding_tasks"

    id = pk_col()
    run_id = Column(
        UUID(as_uuid=True), ForeignKey("onboarding_runs.id", ondelete="CASCADE")
    )
    step_index = Column(Integer)
    title = Column(Text)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"))
    status = Column(Text, default="locked")
    deadline_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("run_id", "step_index", name="uq_onboarding_tasks_run_step"),
        CheckConstraint(
            "status in ('locked','unlocked','in_progress','done')",
            name="onboarding_tasks_status_check",
        ),
        Index("ix_onboarding_tasks_owner_status", "owner_id", "status"),
    )


class Document(Base):
    __tablename__ = "documents"

    id = pk_col()
    owner_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=True)
    doc_category = Column(Text)
    doc_type = Column(Text)
    title = Column(Text)
    version = Column(Integer, default=1)
    change_summary = Column(Text)
    storage_path = Column(Text)
    content_text = Column(Text)
    search_tsv = Column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(title,'') || ' ' || coalesce(content_text,''))",
            persisted=True,
        ),
    )
    visible_roles = Column(ARRAY(Text))
    requires_ack = Column(Boolean, default=False)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("employees.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "doc_category in ('personal','policy')", name="documents_category_check"
        ),
        Index("ix_documents_search_tsv", "search_tsv", postgresql_using="gin"),
        Index("ix_documents_owner_id", "owner_id"),
        Index("ix_documents_category", "doc_category"),
    )


class DocumentAcknowledgement(Base):
    __tablename__ = "document_acknowledgements"

    id = pk_col()
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"))
    acknowledged_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "document_id", "employee_id", name="uq_document_ack_doc_emp"
        ),
    )


class Expense(Base):
    __tablename__ = "expenses"

    id = pk_col()
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"))
    amount = Column(Numeric)
    category = Column(Text)
    description = Column(Text)
    expense_date = Column(Date)
    receipt_path = Column(Text)
    status = Column(Text, default="pending_manager")
    approver_id = Column(UUID(as_uuid=True), nullable=True)
    finance_approver_id = Column(UUID(as_uuid=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("amount > 0", name="expenses_amount_check"),
        CheckConstraint(
            "status in ('submitted','pending_manager','pending_finance','paid','rejected')",
            name="expenses_status_check",
        ),
        Index("ix_expenses_emp_status", "employee_id", "status"),
        Index("ix_expenses_approver_status", "approver_id", "status"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id = pk_col()
    recipient_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"))
    type = Column(Text)
    title = Column(Text)
    body = Column(Text)
    link = Column(Text)
    resource_type = Column(Text)
    resource_id = Column(UUID(as_uuid=True))
    read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index(
            "ix_notifications_recipient_read_created",
            "recipient_id",
            "read",
            "created_at",
        ),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = pk_col()
    actor_id = Column(UUID(as_uuid=True), nullable=True)
    action = Column(Text)
    resource_type = Column(Text)
    resource_id = Column(UUID(as_uuid=True))
    metadata_ = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_actor_created", "actor_id", "created_at"),
    )
