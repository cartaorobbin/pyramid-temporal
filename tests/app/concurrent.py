"""Activities and workflows that probe concurrent activity execution.

Every probe rendezvouses with the other executions of its batch before it looks
at its context, so the assertions in ``tests/test_concurrency.py`` only hold
when the executions really do overlap. Each rendezvous has a timeout, so a
worker that serializes executions fails the activity instead of hanging.
"""

import asyncio
import threading
from datetime import timedelta
from typing import Any, Optional

from pyramid.request import Request
from pyramid.threadlocal import get_current_registry, get_current_request
from temporalio import workflow
from temporalio.common import RetryPolicy

from pyramid_temporal import ActivityContext, activity
from tests.app.models import User

# Task queue used only by the concurrency probes, so they never compete with
# the other integration tests for activity slots.
PROBE_TASK_QUEUE = "pyramid-temporal-concurrency-test"

# Every batch runs exactly two executions, which is the smallest number that
# can expose shared state between them.
PROBE_PARTIES = 2

RENDEZVOUS_TIMEOUT = 15.0


class AsyncRendezvous:
    """Release its waiters only once ``parties`` of them have arrived."""

    def __init__(self, parties: int) -> None:
        self._parties = parties
        self._arrived = 0
        self._released = asyncio.Event()

    def reset(self) -> None:
        """Forget previous arrivals so the next batch starts from zero."""
        self._arrived = 0
        self._released = asyncio.Event()

    async def wait(self, timeout: float) -> None:
        """Block until every party arrives, or raise ``TimeoutError``."""
        self._arrived += 1
        if self._arrived >= self._parties:
            self._released.set()
        await asyncio.wait_for(self._released.wait(), timeout)


class SyncRendezvous:
    """Thread-based counterpart of :class:`AsyncRendezvous`."""

    def __init__(self, parties: int) -> None:
        self._parties = parties
        self._barrier = threading.Barrier(parties)

    def reset(self) -> None:
        """Replace the barrier so the next batch starts from zero."""
        self._barrier = threading.Barrier(self._parties)

    def wait(self, timeout: float) -> None:
        """Block until every party arrives, or raise ``BrokenBarrierError``."""
        self._barrier.wait(timeout)


_async_rendezvous = AsyncRendezvous(PROBE_PARTIES)
_sync_rendezvous = SyncRendezvous(PROBE_PARTIES)


def reset_rendezvous() -> None:
    """Clear the rendezvous state shared by the probes."""
    _async_rendezvous.reset()
    _sync_rendezvous.reset()


def probe_email(label: str) -> str:
    """Return the unique email a probe writes for ``label``."""
    return f"{label}@probe.test"


def _visible_request(context: ActivityContext) -> Optional[Request]:
    """Return the request the context exposes now, or None if it has none.

    A concurrent execution that closed the shared request leaves the context
    empty, and the probe reports that as ``None`` instead of failing, so the
    test sees an assertion about request identity rather than an activity error.
    """
    try:
        request = context.request
    except RuntimeError:
        return None
    return request


def _claim_request(context: ActivityContext, label: str) -> Request:
    """Tag the request this execution starts with, before the rendezvous."""
    request = context.request
    request.probe_label = label
    return request


def _write_probe_row(context: ActivityContext, label: str) -> None:
    """Write this execution's row through the context, like a real activity body.

    Reading the session from the context after the rendezvous is the point: an
    execution that lost its request writes through another one's session.
    """
    session = context.request.dbsession
    session.add(User(name=label, email=probe_email(label)))
    session.flush()


def _report(context: ActivityContext, request: Request, label: str) -> dict[str, Any]:
    """Describe what this execution sees while the other one is still running.

    Everything the body would use is read through the context, so a request
    shared with a concurrent execution shows up as identical ids across reports.
    """
    visible = _visible_request(context)
    return {
        "label": label,
        "request_id": id(request),
        "tm_id": id(getattr(visible, "tm", None)),
        "session_id": id(getattr(visible, "dbsession", None)),
        "request_is_own": visible is request,
        "label_on_context_request": getattr(visible, "probe_label", None),
        "thread_name": threading.current_thread().name,
        "threadlocal_request_is_own": get_current_request() is request,
        "threadlocal_registry_is_app": get_current_registry() is context.registry,
    }


@activity.defn
async def async_probe_activity(context: ActivityContext, label: str) -> dict[str, Any]:
    """Report what an async execution sees while another one overlaps it."""
    request = _claim_request(context, label)
    await _async_rendezvous.wait(RENDEZVOUS_TIMEOUT)
    _write_probe_row(context, label)
    return _report(context, request, label)


@activity.defn
def sync_probe_activity(context: ActivityContext, label: str) -> dict[str, Any]:
    """Report what a sync execution sees while another one overlaps it.

    A plain ``def`` activity must run in Temporal's activity thread pool. Two of
    them can only reach the barrier together when they are off the event loop.
    """
    request = _claim_request(context, label)
    _sync_rendezvous.wait(RENDEZVOUS_TIMEOUT)
    _write_probe_row(context, label)
    return _report(context, request, label)


async def _run_probes(activity_name: str, labels: list[str]) -> list[dict[str, Any]]:
    """Run one probe activity per label, all at the same time."""
    reports = await asyncio.gather(
        *[
            workflow.execute_activity(
                activity_name,
                label,
                schedule_to_close_timeout=timedelta(seconds=60),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            for label in labels
        ]
    )
    return list(reports)


@workflow.defn(sandboxed=False)
class ConcurrentAsyncProbeWorkflow:
    """Run the async probe concurrently, once per label."""

    @workflow.run
    async def run(self, labels: list[str]) -> list[dict[str, Any]]:
        return await _run_probes(async_probe_activity.name, labels)


@workflow.defn(sandboxed=False)
class ConcurrentSyncProbeWorkflow:
    """Run the sync probe concurrently, once per label."""

    @workflow.run
    async def run(self, labels: list[str]) -> list[dict[str, Any]]:
        return await _run_probes(sync_probe_activity.name, labels)
