"""Definition tests: what a decorated activity exposes to workflow code.

Workflow code hands the activity itself to ``workflow.execute_activity``, and
Temporal then reads the activity definition off that object to learn which name
to schedule. These tests pin down that surface, plus the direct call an
activity body needs to be usable as a plain function. No Temporal server and no
database are involved.
"""

import asyncio
from typing import Any

import pytest
from temporalio import activity as temporal_activity

from pyramid_temporal import ActivityContext, activity, activity_execution
from tests.app.deferred_annotation import deferred_annotation_body


@activity.defn
def definition_activity(context: ActivityContext, count: int) -> str:
    """Build a value from the argument, so a direct call can be observed."""
    return f"counted {count}"


@activity.defn(name="custom-definition-name")
async def renamed_definition_activity(context: ActivityContext, count: int) -> str:
    """Same body, async, and under a name of its own."""
    return f"counted {count}"


@activity.defn
def context_only_activity(context: ActivityContext) -> str:
    """An activity the workflow calls with no arguments of its own."""
    return "counted nothing"


def keyword_only_body(*, count: int) -> str:
    """Undecorated: no positional parameter, so no room for the context."""
    return f"counted {count}"


def unbound_body(count: int) -> str:
    """Undecorated: a first parameter that cannot be the context."""
    return f"counted {count}"


def any_context_body(context: Any, count: int) -> str:
    """Undecorated: an annotation that claims nothing about the context."""
    return f"counted {count}"


def unannotated_context_body(context, count: int) -> str:
    """Undecorated: no annotation on the context at all."""
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


def test_definition_argument_types_are_empty_without_arguments_of_its_own():
    """Stripping the context leaves nothing when the context is all there is."""
    defn = temporal_activity._Definition.must_from_callable(context_only_activity)

    assert defn.arg_types == []


def test_an_activity_with_no_positional_parameter_is_refused():
    """Nothing could hold the context, and the definition would describe a lie."""
    with pytest.raises(TypeError, match="takes no positional argument"):
        activity.defn(keyword_only_body)


def test_an_activity_whose_first_parameter_is_not_a_context_is_refused():
    """A body written without the context fails on its first execution otherwise."""
    with pytest.raises(TypeError, match="must be an ActivityContext"):
        activity.defn(unbound_body)


def test_an_annotation_that_only_exists_under_type_checking_is_refused():
    """Temporal converts arguments and results with these, so they must be real."""
    with pytest.raises(TypeError, match="annotation that cannot be resolved"):
        activity.defn(deferred_annotation_body)


@pytest.mark.parametrize(
    "body",
    [any_context_body, unannotated_context_body],
    ids=["any", "unannotated"],
)
def test_a_first_parameter_that_claims_nothing_is_accepted(body):
    """Only an annotation that contradicts the context is refused."""
    assert activity.defn(body).name == body.__name__


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
