#!/usr/bin/env python3
"""Example usage of pyramid-temporal.

This example demonstrates how pyramid-temporal gives every Temporal activity
execution a real Pyramid request with automatic transaction management, and how
to write activities that block without stalling the worker.
"""

import asyncio
import logging
from datetime import timedelta

from pyramid.config import Configurator
from temporalio import workflow
from temporalio.client import Client

from pyramid_temporal import ActivityContext, PyramidEnvironment, Worker, activity, signal_workflow, start_workflow

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TASK_QUEUE = "pyramid-temporal-example"
TEMPORAL_HOST = "localhost:7233"


@activity.defn
async def my_transactional_activity(context: ActivityContext, name: str) -> str:
    """Example async activity with its own request and its own transaction.

    The activity never handles transactions itself. pyramid-temporal begins one
    before the body runs, commits it when the body returns, and aborts it when
    the body raises. Because the request belongs to this execution alone, the
    worker can run many of these at the same time.
    """
    logger.info("Processing activity for: %s", name)

    # Database work would go through this execution's own session:
    # session = context.request.dbsession
    settings = context.request.registry.settings
    logger.info("Activity sees %d settings", len(settings))

    await asyncio.sleep(0.1)

    logger.info("Activity completed successfully")
    return f"Hello, {name}! Transaction managed automatically."


@activity.defn
def my_blocking_activity(context: ActivityContext, name: str) -> str:
    """Example sync activity for a body that blocks.

    A plain ``def`` activity runs in Temporal's activity executor rather than on
    the worker's event loop, so a blocking database call, HTTP request, or gRPC
    call cannot stall the worker or the other activities it is running.
    """
    logger.info("Processing blocking activity for: %s", name)

    # Blocking work belongs here: requests, gRPC, long queries.
    settings = context.request.registry.settings
    logger.info("Blocking activity sees %d settings", len(settings))

    return f"Hello, {name}! Ran off the event loop."


@activity.defn
async def failing_activity(context: ActivityContext) -> str:
    """Example activity that fails, to demonstrate transaction rollback."""
    logger.info("Starting activity that will fail")

    await asyncio.sleep(0.1)

    # This aborts the transaction of this execution, and only of this execution.
    raise ValueError("This activity intentionally fails")


@workflow.defn(sandboxed=False)
class MyWorkflow:
    """Example workflow that uses transactional activities."""

    @workflow.run
    async def run(self, name: str) -> str:
        """Run the workflow with transactional activities."""
        try:
            result = await workflow.execute_activity(
                my_transactional_activity,
                name,
                start_to_close_timeout=timedelta(seconds=60),
            )
        except Exception as e:
            logger.error("Workflow failed: %s", e)
            raise
        else:
            return result


def create_worker(env: PyramidEnvironment, client: Client) -> Worker:
    """Create a worker that runs several activities at the same time.

    ``max_concurrent_activities`` is safe to raise: each execution builds its own
    request, dbsession, and transaction. The worker also creates the thread pool
    that Temporal needs for the sync activity.
    """
    return Worker(
        client,
        env,
        task_queue=TASK_QUEUE,
        workflows=[MyWorkflow],
        activities=[my_transactional_activity, my_blocking_activity, failing_activity],
        max_concurrent_activities=10,
    )


async def main() -> None:
    """Main function to demonstrate the library."""
    logger.info("Starting pyramid-temporal example")

    # A real application bootstraps its own INI file instead:
    # env = PyramidEnvironment.from_bootstrap(bootstrap('development.ini'))
    config = Configurator(settings={"pyramid_temporal.auto_connect": "false"})
    config.include("pyramid_temporal")
    config.commit()
    env = PyramidEnvironment(registry=config.registry)

    client = await Client.connect(TEMPORAL_HOST)
    create_worker(env, client)

    logger.info("Worker created with %d activity slots", 10)
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
        temporal_host=TEMPORAL_HOST,
        namespace="default",
        task_queue=TASK_QUEUE,
        workflow_run=MyWorkflow.run,
        arg="World",
        id="example-workflow-1",
    )
    logger.info("Started workflow, run_id=%s", run_id)

    signal_workflow(
        temporal_host=TEMPORAL_HOST,
        namespace="default",
        workflow_id="example-workflow-1",
        run_id=run_id,
        signal="some_signal",
    )
    logger.info("Signal delivered to workflow")
    return run_id


if __name__ == "__main__":
    asyncio.run(main())
