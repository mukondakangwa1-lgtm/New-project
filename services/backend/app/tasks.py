"""
Celery task placeholders for connector syncing and auto-learner operations.
These are intentionally minimal: they call into application modules if present and
log helpful messages. Implement the actual sync/learn logic in app.core or app.services
and call those functions from here.
"""
import os
from celery_app import celery


@celery.task(bind=True)
def sync_connector(self, connector_id: int):
    """Synchronize a single connector by ID.

    Implement the real sync logic in app.core.connectors.sync_connector(connector_id)
    or similar and call it from here. This task should be idempotent and safe to retry.
    """
    try:
        # Import lazily to avoid import-time side-effects when Celery worker starts
        from app.core.connectors import sync_connector as _sync

        _sync(connector_id)
        return {"status": "ok", "connector_id": connector_id}
    except ImportError:
        # The connectors module is not present or not implemented. Leave this for manual work.
        raise NotImplementedError("Connector sync implementation missing. Implement app.core.connectors.sync_connector")


@celery.task(bind=True)
def run_auto_learner(self):
    """Run the autonomous learning loop once.

    Implement the core logic in app.core.auto_learner.run() and call it here.
    """
    try:
        from app.core.auto_learner import run as _run

        _run()
        return {"status": "ok"}
    except ImportError:
        raise NotImplementedError("Auto-learner implementation missing. Implement app.core.auto_learner.run")
