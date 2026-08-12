"""Concurrency tests: one Pyramid request and one transaction per execution.

Each test starts a workflow that fans out two activity executions on a worker
with ``max_concurrent_activities=2``. The probes rendezvous with each other, so
the executions provably overlap while they report what their context exposes.
"""

import logging

from pyramid_temporal import start_workflow
from tests.app.concurrent import (
    PROBE_TASK_QUEUE,
    ConcurrentAsyncProbeWorkflow,
    ConcurrentSyncProbeWorkflow,
    probe_email,
)
from tests.app.models import User

logger = logging.getLogger(__name__)

NAMESPACE = "default"

# Threads created by the worker for sync activities, see Worker._create_activity_executor.
ACTIVITY_THREAD_PREFIX = "pyramid-temporal-activity"


def test_concurrent_async_activities_keep_their_own_request(concurrent_worker, temporal_host, probe_labels):
    """Overlapping async executions must each keep their own Pyramid request."""
    reports = start_workflow(
        temporal_host=temporal_host,
        namespace=NAMESPACE,
        task_queue=PROBE_TASK_QUEUE,
        workflow_run=ConcurrentAsyncProbeWorkflow.run,
        arg=probe_labels,
        id=f"concurrent-async-request-{probe_labels[0]}",
        wait=True,
    )

    assert [report["request_is_own"] for report in reports] == [True, True]
    assert [report["label_on_context_request"] for report in reports] == probe_labels
    assert len({report["request_id"] for report in reports}) == 2


def test_concurrent_async_activities_commit_their_own_transaction(
    concurrent_worker, temporal_host, probe_labels, dbsession
):
    """Overlapping async executions must each commit their own transaction."""
    reports = start_workflow(
        temporal_host=temporal_host,
        namespace=NAMESPACE,
        task_queue=PROBE_TASK_QUEUE,
        workflow_run=ConcurrentAsyncProbeWorkflow.run,
        arg=probe_labels,
        id=f"concurrent-async-transaction-{probe_labels[0]}",
        wait=True,
    )

    assert len({report["tm_id"] for report in reports}) == 2
    assert len({report["session_id"] for report in reports}) == 2

    dbsession.expire_all()
    emails = [probe_email(label) for label in probe_labels]
    committed = dbsession.query(User).filter(User.email.in_(emails)).all()

    assert sorted(user.name for user in committed) == sorted(probe_labels)


def test_concurrent_sync_activities_run_in_distinct_activity_threads(concurrent_worker, temporal_host, probe_labels):
    """A plain def activity must run in the activity thread pool, two at a time."""
    reports = start_workflow(
        temporal_host=temporal_host,
        namespace=NAMESPACE,
        task_queue=PROBE_TASK_QUEUE,
        workflow_run=ConcurrentSyncProbeWorkflow.run,
        arg=probe_labels,
        id=f"concurrent-sync-threads-{probe_labels[0]}",
        wait=True,
    )

    assert [report["request_is_own"] for report in reports] == [True, True]
    assert len({report["thread_name"] for report in reports}) == 2
    assert all(report["thread_name"].startswith(ACTIVITY_THREAD_PREFIX) for report in reports)


def test_sync_activity_exposes_its_request_to_pyramid_threadlocals(concurrent_worker, temporal_host, probe_labels):
    """A sync execution owns its thread, so get_current_request() is its own request."""
    reports = start_workflow(
        temporal_host=temporal_host,
        namespace=NAMESPACE,
        task_queue=PROBE_TASK_QUEUE,
        workflow_run=ConcurrentSyncProbeWorkflow.run,
        arg=probe_labels,
        id=f"concurrent-sync-threadlocal-{probe_labels[0]}",
        wait=True,
    )

    assert [report["threadlocal_request_is_own"] for report in reports] == [True, True]
    assert [report["threadlocal_registry_is_app"] for report in reports] == [True, True]
