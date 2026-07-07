#!/usr/bin/env python3
"""Example usage of pyramid-temporal.

This example demonstrates how to use pyramid-temporal to automatically
manage transactions in Temporal activities.
"""

import asyncio
import logging

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker

from pyramid_temporal import PyramidTemporalInterceptor, signal_workflow, start_workflow

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@activity.defn
async def my_transactional_activity(name: str) -> str:
    """Example activity that will have automatic transaction management.

    This activity doesn't need to handle transactions manually -
    the PyramidTemporalInterceptor will automatically:
    1. Begin a transaction when the activity starts
    2. Commit the transaction when the activity succeeds
    3. Abort the transaction if the activity fails
    """
    logger.info("Processing activity for: %s", name)

    # Simulate some work that might involve database operations
    await asyncio.sleep(0.1)

    # This would normally be database operations that participate in the transaction
    result = f"Hello, {name}! Transaction managed automatically."

    logger.info("Activity completed successfully")
    return result


@activity.defn
async def failing_activity() -> str:
    """Example activity that will fail to demonstrate transaction rollback."""
    logger.info("Starting activity that will fail")

    # Simulate some work
    await asyncio.sleep(0.1)

    # This will cause the transaction to be automatically rolled back
    raise ValueError("This activity intentionally fails")


@workflow.defn
class MyWorkflow:
    """Example workflow that uses transactional activities."""

    @workflow.run
    async def run(self, name: str) -> str:
        """Run the workflow with transactional activities."""
        try:
            # This activity will succeed and commit its transaction
            result = await workflow.execute_activity(
                my_transactional_activity,
                name,
                schedule_to_close_timeout=60,
                start_to_close_timeout=60,
            )
        except Exception as e:
            logger.error("Workflow failed: %s", e)
            raise
        else:
            return result


async def main() -> None:
    """Main function to demonstrate the library."""
    logger.info("Starting pyramid-temporal example")

    # Create Temporal client
    client = await Client.connect("localhost:7233")

    # Create worker with pyramid-temporal interceptor
    Worker(
        client,
        task_queue="pyramid-temporal-example",
        workflows=[MyWorkflow],
        activities=[my_transactional_activity, failing_activity],
        interceptors=[PyramidTemporalInterceptor()],  # This adds automatic transaction management
    )

    logger.info("Worker created with pyramid-temporal interceptor")
    logger.info("Note: This example requires a running Temporal server")
    logger.info("Start the server with: temporal server start-dev")

    # In a real application, you would run the worker with:
    # await worker.run()

    logger.info("Example setup complete!")
    logger.info(
        "To dispatch a workflow from synchronous code, run start_and_signal_workflow() "
        "with a running Temporal server and worker."
    )


def start_and_signal_workflow() -> str:
    """Start and signal a workflow from synchronous code.

    pyramid-temporal exposes request-free helpers so CLI commands and scripts never
    re-implement Client.connect + asyncio.run themselves. This function is NOT called by
    ``main`` because it requires a running Temporal server AND a running worker to make
    progress; run it manually once both are up.

    Inside a Pyramid view or subscriber, prefer the registered request methods, which read
    connection settings from the registry instead of taking them as arguments::

        run_id = request.temporal_start_workflow(MyWorkflow.run, "World", id="example-workflow-1")
        request.temporal_signal_workflow("example-workflow-1", run_id, "some_signal")

    Those methods read pyramid_temporal.temporal_host, pyramid_temporal.temporal_namespace,
    and pyramid_temporal.task_queue from the registry.
    """
    run_id = start_workflow(
        temporal_host="localhost:7233",
        namespace="default",
        task_queue="pyramid-temporal-example",
        workflow_run=MyWorkflow.run,
        arg="World",
        id="example-workflow-1",
    )
    logger.info("Started workflow, run_id=%s", run_id)

    signal_workflow(
        temporal_host="localhost:7233",
        namespace="default",
        workflow_id="example-workflow-1",
        run_id=run_id,
        signal="some_signal",
    )
    logger.info("Signal delivered to workflow")
    return run_id


if __name__ == "__main__":
    asyncio.run(main())
