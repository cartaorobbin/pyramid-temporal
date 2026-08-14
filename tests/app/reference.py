"""A workflow that references its activity by the decorated object.

This is the usage the README documents. Temporal resolves the activity name from
the object while the workflow task runs, so only a real workflow execution
covers it: nothing fails at import time.
"""

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

from pyramid_temporal import ActivityContext, activity

REFERENCE_TASK_QUEUE = "pyramid-temporal-reference"
TYPED_REFERENCE_TASK_QUEUE = "pyramid-temporal-reference-typed"


@dataclass
class ReferenceResult:
    """Result type an activity declares, and the workflow expects back."""

    message: str


@activity.defn
def reference_activity(context: ActivityContext, message: str) -> str:
    """Echo the message, so the workflow result proves the activity ran."""
    return f"handled {message}"


@activity.defn
def typed_reference_activity(context: ActivityContext, message: str) -> ReferenceResult:
    """Return a declared type, which travels as JSON and comes back converted."""
    return ReferenceResult(message=f"handled {message}")


@workflow.defn(sandboxed=False)
class ActivityReferenceWorkflow:
    """Run the activity by passing the decorated object itself, not its name."""

    @workflow.run
    async def run(self, message: str) -> str:
        return await workflow.execute_activity(
            reference_activity,
            message,
            start_to_close_timeout=timedelta(seconds=30),
        )


@workflow.defn(sandboxed=False)
class TypedActivityReferenceWorkflow:
    """Report the type of the activity result, which only the reference carries.

    Referencing the activity hands Temporal the return type the body declared,
    so the result arrives as that type. A workflow that schedules the activity
    by name has no type to convert with and receives plain JSON.
    """

    @workflow.run
    async def run(self, message: str) -> str:
        result = await workflow.execute_activity(
            typed_reference_activity,
            message,
            start_to_close_timeout=timedelta(seconds=30),
        )
        return type(result).__name__
