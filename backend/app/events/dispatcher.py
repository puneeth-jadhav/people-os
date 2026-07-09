import logging
from typing import Callable, Dict, List

logger = logging.getLogger("peopleos.events")

HANDLERS: Dict[str, List[Callable]] = {}


def on(event: str) -> Callable:
    def _register(func: Callable) -> Callable:
        HANDLERS.setdefault(event, []).append(func)
        return func

    return _register


def emit(event: str, payload: dict, db) -> None:
    """Synchronous dispatch to all registered handlers for an event."""
    for handler in HANDLERS.get(event, []):
        try:
            handler(payload, db)
        except Exception:  # pragma: no cover - defensive
            logger.exception("Handler for event %s failed", event)
