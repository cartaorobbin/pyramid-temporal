"""Synchronous Temporal client helpers.

Pyramid views, event subscribers, and CLI commands run synchronously, but the
Temporal client is async. This module hides the sync->async bridge so callers
never re-implement ``Client.connect`` + ``asyncio.run`` themselves.

The bridge runs each coroutine inside a dedicated worker thread. A fresh
``asyncio.run`` there sidesteps two problems: it never clashes with an event
loop that a caller may already be running (``asyncio.run`` refuses to run inside
a running loop), and a Temporal ``Client`` is bound to the loop that created it,
so it must be connected and used on the same loop.

Two audiences:

- ``start_workflow`` / ``signal_workflow`` are request-free and suit CLI code.
  ``start_workflow`` also accepts ``wait=True`` to block for the workflow result.
- ``request.temporal_start_workflow`` / ``request.temporal_signal_workflow``
  (registered in ``includeme``) read connection settings automatically and suit
  views and subscribers.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Coroutine, Literal, Sequence, TypeVar, overload

from temporalio.client import Client

_T = TypeVar("_T")

# A single dedicated thread is enough: it owns its own event loop per call via
# asyncio.run, and serializing client calls keeps the bridge simple.
_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="temporal-client")


def _run_sync(coro: Coroutine[Any, Any, _T]) -> _T:
    """Run an async coroutine from sync code without touching a running loop."""
    return _pool.submit(asyncio.run, coro).result()


@overload
def start_workflow(
    *,
    temporal_host: str,
    namespace: str,
    task_queue: str,
    workflow_run: Any,
    arg: Any,
    id: str,  # noqa: A002 - mirrors temporalio's start_workflow(id=...) API
    wait: Literal[False] = False,
) -> str:
    ...


@overload
def start_workflow(
    *,
    temporal_host: str,
    namespace: str,
    task_queue: str,
    workflow_run: Any,
    arg: Any,
    id: str,  # noqa: A002 - mirrors temporalio's start_workflow(id=...) API
    wait: Literal[True],
) -> Any:
    ...


def start_workflow(
    *,
    temporal_host: str,
    namespace: str,
    task_queue: str,
    workflow_run: Any,
    arg: Any,
    id: str,  # noqa: A002 - mirrors temporalio's start_workflow(id=...) API
    wait: bool = False,
) -> Any:
    """Connect to Temporal and start a workflow.

    By default this returns the ``run_id`` of the started workflow without waiting.
    Pass ``wait=True`` to block until the workflow completes and return its result
    instead (equivalent to Temporal's ``execute_workflow``).
    """

    async def _run() -> Any:
        client = await Client.connect(temporal_host, namespace=namespace)
        if wait:
            return await client.execute_workflow(workflow_run, arg, id=id, task_queue=task_queue)
        handle = await client.start_workflow(workflow_run, arg, id=id, task_queue=task_queue)
        run_id = handle.first_execution_run_id
        if run_id is None:
            raise RuntimeError(f"Temporal did not return a run id for workflow '{id}'")
        return run_id

    return _run_sync(_run())


def signal_workflow(
    *,
    temporal_host: str,
    namespace: str,
    workflow_id: str,
    run_id: str,
    signal: str,
    args: Sequence[Any] = (),
) -> None:
    """Connect to Temporal and signal a running workflow."""

    async def _signal() -> None:
        client = await Client.connect(temporal_host, namespace=namespace)
        handle = client.get_workflow_handle(workflow_id, run_id=run_id)
        await handle.signal(signal, *args)

    _run_sync(_signal())
