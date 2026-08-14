"""A workflow must reach its activity through the decorated object.

Referencing the activity by name is a workaround; the documented usage is to
pass the activity itself. Resolution happens when the workflow task runs, so
this needs a real workflow execution against a Temporal server.
"""

from tests.app.reference import (
    REFERENCE_TASK_QUEUE,
    TYPED_REFERENCE_TASK_QUEUE,
    ActivityReferenceWorkflow,
    TypedActivityReferenceWorkflow,
    reference_activity,
    typed_reference_activity,
)


def test_workflow_executes_an_activity_referenced_by_its_object(run_workflow):
    """The decorated activity resolves to the name the Worker registered it under."""
    result = run_workflow(
        ActivityReferenceWorkflow,
        "a message",
        activities=[reference_activity],
        task_queue=REFERENCE_TASK_QUEUE,
    )

    assert result == "handled a message"


def test_workflow_converts_the_result_into_the_type_the_activity_declared(run_workflow):
    """The reference carries the return type, so the result is not plain JSON."""
    result = run_workflow(
        TypedActivityReferenceWorkflow,
        "a message",
        activities=[typed_reference_activity],
        task_queue=TYPED_REFERENCE_TASK_QUEUE,
    )

    assert result == "ReferenceResult"
