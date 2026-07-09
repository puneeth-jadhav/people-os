-- PeopleOS schema
create extension if not exists pgcrypto;
create extension if not exists citext;

drop table if exists audit_logs cascade;
drop table if exists notifications cascade;
drop table if exists expenses cascade;
drop table if exists document_acknowledgements cascade;
drop table if exists documents cascade;
drop table if exists onboarding_tasks cascade;
drop table if exists onboarding_runs cascade;
drop table if exists onboarding_templates cascade;
drop table if exists leave_requests cascade;
drop table if exists leave_balances cascade;
drop table if exists leave_rules cascade;
drop table if exists refresh_tokens cascade;
drop table if exists employees cascade;
drop table if exists departments cascade;

create table departments (
    id uuid primary key default gen_random_uuid(),
    name text unique not null,
    head_employee_id uuid null
);

create table employees (
    id uuid primary key default gen_random_uuid(),
    name text,
    email citext unique not null,
    password_hash text,
    role text check (role in ('employee','manager','hr_admin')),
    department_id uuid null references departments(id) on delete restrict,
    manager_id uuid null references employees(id) on delete restrict,
    designation text,
    join_date date,
    status text default 'onboarding' check (status in ('onboarding','active','terminated')),
    employment_type text default 'full_time',
    aadhaar_number text,
    pan_number text,
    created_at timestamptz default now()
);
create index ix_employees_role on employees(role);
create index ix_employees_manager_id on employees(manager_id);
create index ix_employees_department_id on employees(department_id);

-- circular FK: departments.head_employee_id -> employees.id
alter table departments
    add constraint fk_departments_head_employee
    foreign key (head_employee_id) references employees(id) on delete set null;

create table refresh_tokens (
    id uuid primary key default gen_random_uuid(),
    employee_id uuid references employees(id) on delete cascade,
    token_hash text unique not null,
    expires_at timestamptz,
    revoked boolean default false,
    created_at timestamptz default now()
);
create index ix_refresh_tokens_employee_id on refresh_tokens(employee_id);

create table leave_rules (
    id uuid primary key default gen_random_uuid(),
    leave_type text,
    annual_quota numeric,
    accrual_per_month numeric default 0,
    carry_forward_max numeric default 0,
    active boolean default true
);

create table leave_balances (
    id uuid primary key default gen_random_uuid(),
    employee_id uuid references employees(id) on delete restrict,
    leave_type text,
    year int,
    total_days numeric,
    used_days numeric default 0 check (used_days >= 0),
    pending_days numeric default 0 check (pending_days >= 0),
    carry_forward_days numeric default 0,
    unique (employee_id, leave_type, year)
);

create table leave_requests (
    id uuid primary key default gen_random_uuid(),
    employee_id uuid references employees(id) on delete restrict,
    request_type text default 'leave' check (request_type in ('leave','wfh')),
    leave_type text null,
    start_date date,
    end_date date,
    days_requested numeric check (days_requested > 0),
    status text default 'pending' check (status in ('pending','approved','rejected','cancelled')),
    approver_id uuid null references employees(id) on delete restrict,
    reason text null,
    decision_note text null,
    applied_at timestamptz default now(),
    resolved_at timestamptz null,
    check (end_date >= start_date)
);
create index ix_leave_requests_emp_status on leave_requests(employee_id, status);
create index ix_leave_requests_approver_status on leave_requests(approver_id, status);
create index ix_leave_requests_dates on leave_requests(start_date, end_date);
create index ix_leave_requests_emp_applied on leave_requests(employee_id, applied_at);

create table onboarding_templates (
    id uuid primary key default gen_random_uuid(),
    name text,
    role_target text,
    department_id uuid null,
    employment_type text,
    steps jsonb,
    active boolean default true
);

create table onboarding_runs (
    id uuid primary key default gen_random_uuid(),
    employee_id uuid unique references employees(id) on delete restrict,
    template_id uuid references onboarding_templates(id) on delete restrict,
    status text default 'in_progress' check (status in ('in_progress','completed')),
    started_at timestamptz default now(),
    completed_at timestamptz null
);

create table onboarding_tasks (
    id uuid primary key default gen_random_uuid(),
    run_id uuid references onboarding_runs(id) on delete cascade,
    step_index int,
    title text,
    owner_id uuid references employees(id) on delete restrict,
    status text default 'locked' check (status in ('locked','unlocked','in_progress','done')),
    deadline_at timestamptz,
    completed_at timestamptz null,
    unique (run_id, step_index)
);
create index ix_onboarding_tasks_owner_status on onboarding_tasks(owner_id, status);

create table documents (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid null references employees(id) on delete restrict,
    doc_category text check (doc_category in ('personal','policy')),
    doc_type text,
    title text,
    version int default 1,
    change_summary text,
    storage_path text,
    content_text text,
    search_tsv tsvector generated always as (
        to_tsvector('english', coalesce(title,'') || ' ' || coalesce(content_text,''))
    ) stored,
    visible_roles text[],
    requires_ack boolean default false,
    uploaded_by uuid references employees(id) on delete restrict,
    created_at timestamptz default now()
);
create index ix_documents_search_tsv on documents using gin(search_tsv);
create index ix_documents_owner_id on documents(owner_id);
create index ix_documents_category on documents(doc_category);

create table document_acknowledgements (
    id uuid primary key default gen_random_uuid(),
    document_id uuid references documents(id) on delete restrict,
    employee_id uuid references employees(id) on delete restrict,
    acknowledged_at timestamptz default now(),
    unique (document_id, employee_id)
);

create table expenses (
    id uuid primary key default gen_random_uuid(),
    employee_id uuid references employees(id) on delete restrict,
    amount numeric check (amount > 0),
    category text,
    description text,
    expense_date date,
    receipt_path text,
    status text default 'pending_manager' check (status in ('submitted','pending_manager','pending_finance','paid','rejected')),
    approver_id uuid null,
    finance_approver_id uuid null,
    submitted_at timestamptz default now(),
    resolved_at timestamptz null
);
create index ix_expenses_emp_status on expenses(employee_id, status);
create index ix_expenses_approver_status on expenses(approver_id, status);

create table notifications (
    id uuid primary key default gen_random_uuid(),
    recipient_id uuid references employees(id) on delete restrict,
    type text,
    title text,
    body text,
    link text,
    resource_type text,
    resource_id uuid,
    read boolean default false,
    created_at timestamptz default now()
);
create index ix_notifications_recipient_read_created on notifications(recipient_id, read, created_at);

create table audit_logs (
    id uuid primary key default gen_random_uuid(),
    actor_id uuid null,
    action text,
    resource_type text,
    resource_id uuid,
    metadata jsonb,
    created_at timestamptz default now()
);
create index ix_audit_logs_resource on audit_logs(resource_type, resource_id);
create index ix_audit_logs_actor_created on audit_logs(actor_id, created_at);
