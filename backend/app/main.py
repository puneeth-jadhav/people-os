from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.shared.responses import ok, register_exception_handlers

# Import event handlers so @on registrations run at startup.
import app.events.handlers  # noqa: F401

from app.analytics.router import router as analytics_router
from app.audit.router import router as audit_router
from app.auth.router import router as auth_router
from app.dashboard.router import router as dashboard_router
from app.documents.router import router as documents_router
from app.employees.router import router as employees_router
from app.expenses.router import router as expenses_router
from app.leaves.router import router as leaves_router
from app.notifications.router import router as notifications_router
from app.onboarding.router import router as onboarding_router
from app.requests_history.router import router as requests_history_router

app = FastAPI(title="PeopleOS API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(employees_router)
app.include_router(leaves_router)
app.include_router(requests_history_router)
app.include_router(onboarding_router)
app.include_router(expenses_router)
app.include_router(documents_router)
app.include_router(notifications_router)
app.include_router(audit_router)
app.include_router(analytics_router)


@app.get("/api/v1/health")
def health():
    return ok({"status": "ok"})
