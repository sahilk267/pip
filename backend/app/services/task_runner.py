"""In-process background task runner — thread-pool based, no Redis required."""
from __future__ import annotations

import logging
import queue
import threading
import time
import traceback
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ─── Task Result Store ────────────────────────────────────────────────────────
_results: dict[str, dict[str, Any]] = {}
_results_lock = threading.Lock()
_task_queue: queue.Queue[dict[str, Any]] = queue.Queue()
_running = threading.Event()
_workers: list[threading.Thread] = []

MAX_RESULTS = 500
WORKER_COUNT = 3


def _task_worker():
    """Worker loop that processes tasks from the queue."""
    while _running.is_set():
        try:
            task = _task_queue.get(timeout=1.0)
        except queue.Empty:
            continue
        task_id = task["id"]
        fn = task["fn"]
        args = task.get("args", ())
        kwargs = task.get("kwargs", {})
        with _results_lock:
            _results[task_id] = {"status": "running", "started_at": datetime.now(timezone.utc).isoformat()}
        try:
            result = fn(*args, **kwargs)
            with _results_lock:
                _results[task_id] = {
                    "status": "success",
                    "result": result,
                    "started_at": _results[task_id].get("started_at"),
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }
        except Exception as exc:
            logger.error("Task %s failed: %s\n%s", task_id, exc, traceback.format_exc())
            with _results_lock:
                _results[task_id] = {
                    "status": "failed",
                    "error": str(exc),
                    "started_at": _results[task_id].get("started_at"),
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }
        finally:
            _task_queue.task_done()
            # Trim old results
            with _results_lock:
                if len(_results) > MAX_RESULTS:
                    oldest = sorted(_results.items(), key=lambda x: x[1].get("finished_at", ""))[: len(_results) - MAX_RESULTS]
                    for k, _ in oldest:
                        del _results[k]


def start_workers(count: int = WORKER_COUNT):
    """Start background worker threads."""
    global _workers
    _running.set()
    for i in range(count):
        t = threading.Thread(target=_task_worker, name=f"task-worker-{i}", daemon=True)
        t.start()
        _workers.append(t)
    logger.info("Task runner started with %d workers", count)


def stop_workers():
    """Signal workers to stop and wait for them."""
    _running.clear()
    for t in _workers:
        t.join(timeout=3.0)
    _workers.clear()
    logger.info("Task runner stopped")


def enqueue(fn: Callable, *args, task_id: str | None = None, **kwargs) -> str:
    """Enqueue a function call as a background task. Returns task_id."""
    import uuid
    tid = task_id or f"task_{uuid.uuid4().hex[:12]}"
    with _results_lock:
        _results[tid] = {"status": "queued", "queued_at": datetime.now(timezone.utc).isoformat()}
    _task_queue.put({"id": tid, "fn": fn, "args": args, "kwargs": kwargs})
    return tid


def get_result(task_id: str) -> dict[str, Any] | None:
    """Get the current status/result of a task."""
    with _results_lock:
        return _results.get(task_id)


def list_tasks(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """List recent task results."""
    with _results_lock:
        items = list(_results.items())
    if status:
        items = [(k, v) for k, v in items if v.get("status") == status]
    items.sort(key=lambda x: x[1].get("queued_at", x[1].get("started_at", "")), reverse=True)
    return [{"task_id": k, **v} for k, v in items[:limit]]


# ─── Scheduled Task Runner ────────────────────────────────────────────────────

_schedule_thread: threading.Thread | None = None
_scheduled_tasks: list[dict[str, Any]] = []


def schedule(fn: Callable, interval_seconds: int, name: str | None = None, **kwargs):
    """Register a function to run on a fixed interval."""
    _scheduled_tasks.append({
        "fn": fn,
        "interval": interval_seconds,
        "name": name or fn.__name__,
        "kwargs": kwargs,
        "last_run": 0.0,
    })


def _scheduler_loop():
    """Periodic scheduler that enqueues scheduled tasks when their interval elapses."""
    while _running.is_set():
        now = time.time()
        for task in _scheduled_tasks:
            if now - task["last_run"] >= task["interval"]:
                task["last_run"] = now
                try:
                    enqueue(task["fn"], **task["kwargs"])
                except Exception as exc:
                    logger.error("Scheduler enqueue error for %s: %s", task["name"], exc)
        time.sleep(5)


def start_scheduler():
    """Start the periodic scheduler thread."""
    global _schedule_thread
    if not _running.is_set():
        start_workers()
    _schedule_thread = threading.Thread(target=_scheduler_loop, name="task-scheduler", daemon=True)
    _schedule_thread.start()
    logger.info("Task scheduler started with %d scheduled tasks", len(_scheduled_tasks))
