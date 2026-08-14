"""Definition tests: what a decorated activity exposes to workflow code.

Workflow code hands the activity itself to ``workflow.execute_activity``, and
Temporal then reads the activity definition off that object to learn which name
to schedule. These tests pin down that surface, plus the direct call an
activity body needs to be usable as a plain function. No Temporal server and no
database are involved.
"""

import asyncio

import pytest
from temporalio import activity as temporal_activity

from pyramid_temporal import ActivityContext, activity, activity_execution


@activity.defn
def definition_activity(context: ActivityContext, count: int) -> str:
    """Build a value from the argument, so a direct call can be observed."""
    return f"counted {count}"


@activity.defn(name="custom-definition-name")
async def renamed_definition_activity(context: ActivityContext, count: int) -> str:
    """Same body, async, and under a name of its own."""
    return f"counted {count}"


def test_decorated_activity_is_callable():
    """Temporal only resolves a definition from a string or a callable."""
    assert callable(definition_activity)


def test_calling_a_sync_activity_runs_its_body(pyramid_env):
    """An activity body is callable directly, given an execution to run in."""
    with activity_execution(pyramid_env, threadlocal_request=True) as context:
        result = definition_activity(context, 3)

    assert result == "counted 3"


def test_calling_an_async_activity_awaits_its_body(pyramid_env):
    """An async body is returned as its coroutine, so the caller awaits it."""
    with activity_execution(pyramid_env, threadlocal_request=False) as context:
        result = asyncio.run(renamed_definition_activity(context, 4))

    assert result == "counted 4"


def test_calling_an_activity_without_a_context_is_refused():
    """A first argument that is not a context means nothing bound the activity.

    That is what a plain ``temporalio.worker.Worker`` would do with it, and the
    body would then run with no Pyramid request and no transaction.
    """
    with pytest.raises(TypeError, match="pyramid_temporal.Worker"):
        definition_activity(3)


def test_temporal_resolves_the_activity_name():
    """The definition carries the name the Worker registers the activity under."""
    defn = temporal_activity._Definition.must_from_callable(definition_activity)

    assert defn.name == definition_activity.name == "definition_activity"


def test_temporal_resolves_a_custom_activity_name():
    """A ``name=`` on the decorator reaches the definition too."""
    defn = temporal_activity._Definition.must_from_callable(renamed_definition_activity)

    assert defn.name == "custom-definition-name"


def test_definition_argument_types_exclude_the_activity_context():
    """The context is injected by the binding, so a caller never sends it."""
    defn = temporal_activity._Definition.must_from_callable(definition_activity)

    assert defn.arg_types == [int]


def test_definition_carries_the_declared_return_type():
    """The workflow converts the activity result with this type."""
    defn = temporal_activity._Definition.must_from_callable(definition_activity)

    assert defn.ret_type is str


@pytest.mark.parametrize(
    ("act", "expected"),
    [(definition_activity, False), (renamed_definition_activity, True)],
    ids=["sync", "async"],
)
def test_definition_reports_whether_the_body_is_async(act, expected):
    """The definition agrees with the flavour the Worker binds."""
    defn = temporal_activity._Definition.must_from_callable(act)

    assert defn.is_async is expected
