"""
api_celery.py
=============
Approach 2 -- FastAPI + Celery with Redis broker.

The API server is completely decoupled from the heavy join workload.
It simply enqueues a task and queries Celery for status.

Prerequisites:
    1. Redis running on localhost:6379
    2. Celery worker running:
       celery -A celery_worker worker --loglevel=info --pool=solo

Run:
    uvicorn api_celery:app --host 0.0.0.0 --port 8001 --reload
"""

import logging

from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException

from celery_worker import celery_app, run_join_task

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Data Join API -- Celery Approach",
    description=(
        "Triggers an out-of-core CSV join via a Celery worker backed by Redis. "
        "The API server stays lightweight and fully responsive."
    ),
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_STATE_MAP = {
    "PENDING": "pending",
    "STARTED": "running",
    "RUNNING": "running",
    "SUCCESS": "completed",
    "FAILURE": "failed",
    "REVOKED": "cancelled",
}


def _normalise_state(celery_state: str) -> str:
    return _STATE_MAP.get(celery_state, celery_state.lower())


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/trigger-join", status_code=202)
async def trigger_join():
    """
    Enqueue a data-join task on the Celery worker.

    Returns a ``job_id`` immediately (HTTP 202 Accepted).
    """
    task = run_join_task.delay()
    logger.info("Job %s -- enqueued via Celery", task.id)
    return {"job_id": task.id}


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """
    Query Celery for the current status of a job.
    """
    result = AsyncResult(job_id, app=celery_app)

    response = {
        "job_id": job_id,
        "status": _normalise_state(result.state),
    }

    if result.state == "SUCCESS":
        response["result"] = result.result
    elif result.state == "FAILURE":
        response["error"] = str(result.result)
    elif result.info and isinstance(result.info, dict):
        response["detail"] = result.info.get("detail")

    return response


@app.get("/health")
async def health():
    """Simple health-check."""
    return {"status": "ok", "approach": "Celery + Redis"}
