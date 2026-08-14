"""A workflow that references its activity by the decorated object.

This is the usage the README documents. Temporal resolves the activity name from
the object while the workflow task runs, so only a real workflow execution
covers it: nothing fails at import time.
"""

from datetime import timedelta

from temporalio import workflow

from pyramid_temporal import ActivityContext, activity

REFERENCE_TASK_QUEUE = "pyramid-temporal-reference"


@activity.defn
def reference_activity(context: ActivityContext, message: str) -> str:
    """Echo the message, so the workflow result proves the activity ran."""
    return f"handled {message}"


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
