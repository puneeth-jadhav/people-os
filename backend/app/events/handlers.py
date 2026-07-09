import logging

from app.events.dispatcher import on

logger = logging.getLogger("peopleos.events")


@on("employee.created")
def handle_employee_created(payload: dict, db) -> None:
    logger.info("employee.created: %s", payload)


@on("onboarding.task_completed")
def handle_onboarding_task_completed(payload: dict, db) -> None:
    logger.info("onboarding.task_completed: %s", payload)


@on("request.submitted")
def handle_request_submitted(payload: dict, db) -> None:
    logger.info("request.submitted: %s", payload)


@on("request.approved")
def handle_request_approved(payload: dict, db) -> None:
    logger.info("request.approved: %s", payload)


@on("request.rejected")
def handle_request_rejected(payload: dict, db) -> None:
    logger.info("request.rejected: %s", payload)


@on("expense.submitted")
def handle_expense_submitted(payload: dict, db) -> None:
    logger.info("expense.submitted: %s", payload)


@on("expense.manager_approved")
def handle_expense_manager_approved(payload: dict, db) -> None:
    logger.info("expense.manager_approved: %s", payload)


@on("expense.finance_approved")
def handle_expense_finance_approved(payload: dict, db) -> None:
    logger.info("expense.finance_approved: %s", payload)


@on("expense.pending_finance")
def handle_expense_pending_finance(payload: dict, db) -> None:
    logger.info("expense.pending_finance: %s", payload)


@on("expense.paid")
def handle_expense_paid(payload: dict, db) -> None:
    logger.info("expense.paid: %s", payload)


@on("expense.rejected")
def handle_expense_rejected(payload: dict, db) -> None:
    logger.info("expense.rejected: %s", payload)


@on("policy.published")
def handle_policy_published(payload: dict, db) -> None:
    logger.info("policy.published: %s", payload)


@on("policy.acknowledged")
def handle_policy_acknowledged(payload: dict, db) -> None:
    logger.info("policy.acknowledged: %s", payload)


@on("document.downloaded")
def handle_document_downloaded(payload: dict, db) -> None:
    logger.info("document.downloaded: %s", payload)
