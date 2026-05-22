"""
api_background_tasks.py
=======================
Approach 1 -- FastAPI BackgroundTasks

The join is executed inside the same process using FastAPI's built-in
BackgroundTasks mechanism.  Simple, zero-infrastructure, but the heavy
workload shares resources with the web server.

Run:
    uvicorn api_background_tasks:app --host 0.0.0.0 --port 8000 --reload
"""

import logging
import os
import threading
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, FastAPI, HTTPException

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
# App & in-memory job store
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Data Join API -- BackgroundTasks Approach",
    description=(
        "Triggers an out-of-core CSV join via DuckDB and tracks job status. "
        "Uses FastAPI's built-in BackgroundTasks for non-blocking execution."
    ),
    version="1.0.0",
)

# job_id -> { status, created_at, started_at, completed_at, result, error }
jobs: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Concurrency limiter -- only 1 join at a time to stay within 256 MB RAM
# ---------------------------------------------------------------------------
MAX_CONCURRENT_JOINS = 1
_join_semaphore = threading.Semaphore(MAX_CONCURRENT_JOINS)


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------
def _run_join(job_id: str) -> None:
    """Execute the join and update the job record."""
    acquired = _join_semaphore.acquire(timeout=0)
    if not acquired:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = "Another join is already running. Try again later."
        jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        logger.warning("Job %s -- rejected (concurrency limit reached)", job_id)
        return

    jobs[job_id]["status"] = "running"
    jobs[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()
    logger.info("Job %s -- started", job_id)

    try:
        output_file = os.path.join(join_service.BASE_DIR, f"result_{job_id}.csv")
        result = join_service.perform_join(output_path=output_file)
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["result"] = result
        logger.info("Job %s -- completed: %s", job_id, result)
    except Exception as exc:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(exc)
        logger.exception("Job %s -- failed", job_id)
    finally:
        jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        _join_semaphore.release()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/trigger-join", status_code=202)
async def trigger_join(background_tasks: BackgroundTasks):
    """
    Trigger a background data join.

    Returns a ``job_id`` immediately (HTTP 202 Accepted).
    """
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": None,
        "completed_at": None,
        "result": None,
        "error": None,
    }
    background_tasks.add_task(_run_join, job_id)
    logger.info("Job %s -- queued via BackgroundTasks", job_id)
    return {"job_id": job_id}


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """Return the current status and metadata of a job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **jobs[job_id]}


@app.get("/health")
async def health():
    """Simple health-check."""
    return {
        "status": "ok",
        "approach": "BackgroundTasks",
        "max_concurrent_joins": MAX_CONCURRENT_JOINS,
    }
