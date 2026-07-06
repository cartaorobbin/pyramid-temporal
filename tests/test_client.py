"""Tests for the synchronous Temporal client helpers."""

import uuid

import pytest
from pyramid.request import Request, apply_request_extensions

from pyramid_temporal import _client_settings, start_workflow
from tests.app.models import User
from tests.app.workflows import UserEnrichmentWorkflow


@pytest.mark.parametrize(
    "extra_settings, expected",
    [
        ({}, ("localhost:7233", "default", "default")),
        ({"pyramid_temporal.temporal_host": "temporal:1234"}, ("temporal:1234", "default", "default")),
        ({"pyramid_temporal.namespace": "alias-ns"}, ("localhost:7233", "alias-ns", "default")),
        ({"pyramid_temporal.temporal_namespace": "canon-ns"}, ("localhost:7233", "canon-ns", "default")),
        (
            {"pyramid_temporal.namespace": "alias-ns", "pyramid_temporal.temporal_namespace": "canon-ns"},
            ("localhost:7233", "alias-ns", "default"),
        ),
        ({"pyramid_temporal.task_queue": "payments"}, ("localhost:7233", "default", "payments")),
    ],
    ids=["defaults", "host", "namespace-alias", "namespace-canonical", "alias-precedence", "task-queue"],
)
def test_client_settings_resolution(configured_request, extra_settings, expected):
    """_client_settings resolves host, namespace (alias wins), and task_queue."""
    request = configured_request(extra_settings)

    assert _client_settings(request) == expected


def test_includeme_registers_client_request_methods(configured_request):
    """includeme wires the start/signal workflow request methods."""
    request = configured_request()

    assert callable(request.temporal_start_workflow)
    assert callable(request.temporal_signal_workflow)


def test_start_workflow_returns_run_id(temporal_client, temporal_host):
    """The low-level start_workflow connects and returns the started run_id.

    Gated on temporal_client so it is skipped when no Temporal server is available.
    """
    run_id = start_workflow(
        temporal_host=temporal_host,
        namespace="default",
        task_queue="pyramid-temporal-test",
        workflow_run=UserEnrichmentWorkflow.run,
        arg=1,
        id=f"client-test-{uuid.uuid4().hex[:8]}",
    )

    assert isinstance(run_id, str)
    assert run_id


def test_start_workflow_wait_returns_result(temporal_worker, temporal_host, dbsession):
    """start_workflow(wait=True) blocks until the workflow finishes and returns its result.

    Gated on temporal_worker (which needs a Temporal server) so it is skipped when no
    server is available. The worker shares the test session, so the enriched user is
    visible to the activity.
    """
    user = User(name="Wait Tester", email=f"wait-{uuid.uuid4().hex[:8]}@example.com")
    dbsession.add(user)
    dbsession.flush()

    result = start_workflow(
        temporal_host=temporal_host,
        namespace="default",
        task_queue="pyramid-temporal-test",
        workflow_run=UserEnrichmentWorkflow.run,
        arg=user.id,
        id=f"client-wait-{uuid.uuid4().hex[:8]}",
        wait=True,
    )

    assert result is True


def test_request_temporal_start_workflow_returns_run_id(pyramid_app, temporal_client):
    """request.temporal_start_workflow starts a workflow using registry settings.

    Gated on temporal_client so it is skipped when no Temporal server is available.
    """
    request = Request.blank("/")
    request.registry = pyramid_app.registry
    apply_request_extensions(request)

    run_id = request.temporal_start_workflow(
        UserEnrichmentWorkflow.run,
        1,
        id=f"client-req-{uuid.uuid4().hex[:8]}",
    )

    assert isinstance(run_id, str)
    assert run_id
