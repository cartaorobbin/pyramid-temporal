"""Lifecycle logs for a named activity execution.

These run the bound wrapper directly, without a Temporal server or a database,
and read the log lines an operator would see on an activity thread.
"""

import asyncio
import logging

import pytest

from pyramid_temporal import ActivityContext, activity

STARTED = "Activity batch_process_chunk started"
FINISHED = "Activity batch_process_chunk finished"
COMMITTED = "Transaction committed successfully"
FAILED = "Activity batch_process_chunk failed: chunk failed"
ABORTED = "Transaction aborted successfully"


@activity.defn(name="batch_process_chunk")
def sync_named_activity(context: ActivityContext) -> str:
    """Return so the execution can commit."""
    return "ok"


@activity.defn(name="batch_process_chunk")
async def async_named_activity(context: ActivityContext) -> str:
    """Return so the async execution can commit."""
    return "ok"


@activity.defn(name="batch_process_chunk")
def failing_named_activity(context: ActivityContext) -> None:
    """Raise so the execution logs a failure."""
    raise RuntimeError("chunk failed")


def _record(caplog: pytest.LogCaptureFixture, message: str) -> logging.LogRecord:
    return caplog.records[caplog.messages.index(message)]


def test_sync_activity_logs_start_then_commit_then_finish(transactional_pyramid_env, caplog):
    """A sync execution names the activity before the commit line and after it."""
    caplog.set_level(logging.INFO)
    bound = sync_named_activity.bind(transactional_pyramid_env)

    assert bound() == "ok"

    assert caplog.messages.index(STARTED) < caplog.messages.index(COMMITTED) < caplog.messages.index(FINISHED)
    started = _record(caplog, STARTED)
    finished = _record(caplog, FINISHED)
    assert started.name == "pyramid_temporal.execution"
    assert started.levelno == logging.INFO
    assert finished.name == "pyramid_temporal.execution"
    assert finished.levelno == logging.INFO


def test_async_activity_logs_start_then_commit_then_finish(transactional_pyramid_env, caplog):
    """An async execution uses the same logs, so both wrappers pass the name."""
    caplog.set_level(logging.INFO)
    bound = async_named_activity.bind(transactional_pyramid_env)

    assert asyncio.run(bound()) == "ok"

    assert caplog.messages.index(STARTED) < caplog.messages.index(COMMITTED) < caplog.messages.index(FINISHED)
    started = _record(caplog, STARTED)
    finished = _record(caplog, FINISHED)
    assert started.name == "pyramid_temporal.execution"
    assert started.levelno == logging.INFO
    assert finished.name == "pyramid_temporal.execution"
    assert finished.levelno == logging.INFO


def test_activity_logs_failure_and_aborts_when_a_transaction_manager_exists(transactional_pyramid_env, caplog):
    """A raised body names the activity, aborts, and does not commit."""
    caplog.set_level(logging.DEBUG, logger="pyramid_temporal")
    bound = failing_named_activity.bind(transactional_pyramid_env)

    with pytest.raises(RuntimeError, match="chunk failed"):
        bound()

    failed = _record(caplog, FAILED)
    assert failed.name == "pyramid_temporal.execution"
    assert failed.levelno == logging.WARNING
    assert ABORTED in caplog.messages
    assert COMMITTED not in caplog.messages
    assert "Activity failed with exception" not in caplog.text


def test_activity_logs_failure_without_a_transaction_manager(pyramid_env, caplog):
    """A raised body still names the activity when nothing is configured to abort."""
    caplog.set_level(logging.DEBUG, logger="pyramid_temporal")
    bound = failing_named_activity.bind(pyramid_env)

    with pytest.raises(RuntimeError, match="chunk failed"):
        bound()

    failed = _record(caplog, FAILED)
    assert failed.name == "pyramid_temporal.execution"
    assert failed.levelno == logging.WARNING
    assert ABORTED not in caplog.messages
    assert "Aborting transaction" not in caplog.text
    assert "Activity failed with exception" not in caplog.text
