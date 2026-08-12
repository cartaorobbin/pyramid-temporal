"""Binding tests: what a single activity execution owns and exposes.

These run the bound wrapper directly, without a Temporal server or a database,
so they pin down the execution scope: a fresh request per call, the threadlocal
semantics of each mode, and the teardown that follows the call.
"""

import asyncio
import inspect

import pytest
from pyramid.threadlocal import get_current_registry, get_current_request

from pyramid_temporal import ActivityContext, activity


@activity.defn
def sync_binding_activity(context: ActivityContext) -> dict:
    """Report what a sync activity execution can see."""
    return {
        "context": context,
        "request": context.request,
        "threadlocal_request": get_current_request(),
        "threadlocal_registry": get_current_registry(),
    }


@activity.defn
async def async_binding_activity(context: ActivityContext) -> dict:
    """Report what an async activity execution can see."""
    return {
        "context": context,
        "request": context.request,
        "threadlocal_request": get_current_request(),
        "threadlocal_registry": get_current_registry(),
    }


def test_sync_activity_binds_to_a_plain_callable(pyramid_env):
    """A def activity stays sync, so Temporal runs it in the activity thread pool."""
    bound = sync_binding_activity.bind(pyramid_env)

    assert not inspect.iscoroutinefunction(bound)


def test_async_activity_binds_to_a_coroutine_function(pyramid_env):
    """An async def activity stays async, so Temporal runs it on the event loop."""
    bound = async_binding_activity.bind(pyramid_env)

    assert inspect.iscoroutinefunction(bound)


def test_each_execution_gets_its_own_request(pyramid_env):
    """Two executions of the same bound activity never share a request."""
    bound = sync_binding_activity.bind(pyramid_env)

    first = bound()
    second = bound()

    assert first["request"] is not second["request"]
    assert first["context"] is not second["context"]


def test_sync_execution_publishes_its_request_to_pyramid_threadlocals(pyramid_env):
    """A sync execution owns its thread, so get_current_request() is its request."""
    bound = sync_binding_activity.bind(pyramid_env)

    report = bound()

    assert report["threadlocal_request"] is report["request"]
    assert report["threadlocal_registry"] is pyramid_env.registry


def test_async_execution_publishes_only_the_registry_to_pyramid_threadlocals(pyramid_env):
    """Async executions share the event loop thread, so no request is published.

    Pyramid's threadlocal stack is per-thread and cannot isolate concurrent
    coroutines, so get_current_request() reports nothing rather than another
    execution's request. The registry is worker-wide and stays available.
    """
    bound = async_binding_activity.bind(pyramid_env)

    report = asyncio.run(bound())

    assert report["threadlocal_request"] is None
    assert report["threadlocal_registry"] is pyramid_env.registry


def test_request_is_unavailable_once_the_execution_finished(pyramid_env):
    """The execution scope ends with the call, and the context says so."""
    bound = sync_binding_activity.bind(pyramid_env)

    context = bound()["context"]

    with pytest.raises(RuntimeError, match="outside of activity execution"):
        assert context.request


def test_pyramid_threadlocals_are_restored_after_the_execution(pyramid_env):
    """Nothing of the execution is left behind on the thread."""
    bound = sync_binding_activity.bind(pyramid_env)

    bound()

    assert get_current_request() is None
    assert get_current_registry() is not pyramid_env.registry
