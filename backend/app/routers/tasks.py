"""Background task monitoring router."""
from __future__ import annotations

from fastapi import APIRouter, Query
from typing import Any

from ..services import task_runner

router = APIRouter(prefix='/api/v1/tasks', tags=['tasks'])


@router.get('/', summary='List background tasks')
def list_tasks(
    status: str | None = Query(default=None, description='Filter by status: queued|running|success|failed'),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """List recent background task results."""
    return task_runner.list_tasks(status=status, limit=limit)


@router.get('/{task_id}', summary='Get task status')
def get_task(task_id: str) -> dict[str, Any]:
    """Get the status and result of a specific background task."""
    result = task_runner.get_result(task_id)
    if result is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f'Task {task_id!r} not found')
    return {'task_id': task_id, **result}


@router.get('/stats/summary', summary='Task runner stats')
def task_stats() -> dict[str, Any]:
    """Summary of background task runner statistics."""
    all_tasks = task_runner.list_tasks(limit=500)
    by_status: dict[str, int] = {}
    for t in all_tasks:
        s = t.get('status', 'unknown')
        by_status[s] = by_status.get(s, 0) + 1
    return {
        'total': len(all_tasks),
        'by_status': by_status,
        'workers': task_runner.WORKER_COUNT,
        'scheduled_tasks': len(task_runner._scheduled_tasks),
        'queue_size': task_runner._task_queue.qsize(),
    }
