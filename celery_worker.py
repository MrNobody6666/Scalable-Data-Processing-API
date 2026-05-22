"""
celery_worker.py
================
Celery worker that executes the DuckDB join as a distributed task.

Prerequisites:
    Redis running on localhost:6379

Start the worker:
    celery -A celery_worker worker --loglevel=info --pool=solo
"""

import logging
import os

from celery import Celery

import join_service

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Celery application
# ---------------------------------------------------------------------------
celery_app = Celery(
    "worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,          # enables the STARTED state
    result_expires=3600,              # results expire after 1 hour
    worker_max_tasks_per_child=50,    # recycle workers to free memory
)


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------
@celery_app.task(bind=True, name="join_task")
def run_join_task(self):
    """
    Execute the out-of-core CSV join via DuckDB.

    The task updates its Celery state so the API can report progress.
    """
    logger.info("Celery task %s -- starting join", self.request.id)

    self.update_state(state="RUNNING", meta={"detail": "Join in progress"})

    try:
        output_file = os.path.join(join_service.BASE_DIR, f"result_{self.request.id}.csv")
        result = join_service.perform_join(output_path=output_file)
        logger.info("Celery task %s -- completed: %s", self.request.id, result)
        return result
    except Exception as exc:
        logger.exception("Celery task %s -- failed", self.request.id)
        self.update_state(state="FAILURE", meta={"error": str(exc)})
        raise
