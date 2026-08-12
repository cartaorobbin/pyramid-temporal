"""Example worker factory for use with ptemporal-worker command.

This demonstrates how to create a worker factory function that can be used
with the ptemporal-worker CLI command, using the new pyramid-temporal API.

Usage:
    ptemporal-worker examples/basic/development.ini examples.basic.worker.create_worker
"""

import logging
from datetime import timedelta

from temporalio import workflow

from pyramid_temporal import ActivityContext, PyramidEnvironment, Worker, activity

logger = logging.getLogger(__name__)


# Example activity using the new pyramid-temporal decorator
# The context is automatically injected by the Worker
@activity.defn
async def example_activity(context: ActivityContext, message: str) -> str:
    """Example activity that demonstrates context injection.

    The ActivityContext provides:
    - context.request.dbsession: Database session for this activity
    - context.request.tm: Transaction manager
    - context.request.settings: Application settings
    - context.registry: Full Pyramid registry access
    """
    logger.info("Processing message: %s", message)

    # Access settings from context
    settings = context.request.settings
    logger.info("Got settings: %s keys", len(settings))

    # Access database session (if configured)
    # session = context.request.dbsession
    # user = session.query(User).filter_by(id=user_id).first()

    # Your business logic here - database operations will be transactional
    return f"Processed: {message}"


@activity.defn
def database_activity(context: ActivityContext, user_id: int) -> dict:
    """Example activity that uses the database session.

    Written as a plain ``def``, so Temporal runs it in its activity executor and
    the blocking database calls never occupy the worker's event loop.
    """
    logger.info("Looking up user: %s", user_id)

    # Get database session from context

    # Example query (uncomment when you have a User model):
    # user = session.query(User).filter_by(id=user_id).first()
    # if user:
    #     return {"id": user.id, "name": user.name}

    return {"id": user_id, "name": "Example User"}


@workflow.defn(sandboxed=False)
class ExampleWorkflow:
    """Example workflow."""

    @workflow.run
    async def run(self, message: str) -> str:
        """Run the example workflow."""
        return await workflow.execute_activity(
            example_activity, message, schedule_to_close_timeout=timedelta(seconds=60)
        )


def create_worker(env: PyramidEnvironment) -> Worker:
    """Worker factory function for ptemporal-worker command.

    The command bootstraps the INI file and calls this function with the
    resulting PyramidEnvironment.

    The Worker automatically:
    - Gives each activity execution its own Pyramid request
    - Manages a transaction per execution
    - Creates the thread pool that sync activities need

    Args:
        env: PyramidEnvironment with pyramid-temporal already configured

    Returns:
        Worker: Configured pyramid-temporal Worker instance
    """
    logger.info("Creating example worker")

    # Get Temporal client from registry (created by pyramid-temporal includeme)
    temporal_client = env.registry.get("temporal_client")

    if not temporal_client:
        raise RuntimeError(
            "Temporal client not found in registry. "
            "Make sure pyramid-temporal is properly configured in your INI file "
            "and pyramid_temporal.auto_connect is set to true."
        )

    # Create worker with pyramid-temporal - context binding is automatic!
    worker = Worker(
        temporal_client,
        env,
        task_queue="example-queue",
        workflows=[ExampleWorkflow],
        activities=[example_activity, database_activity],
        max_concurrent_activities=10,
    )

    logger.info("Example worker created successfully")
    return worker


# Alternative factory for different task queue
def create_priority_worker(env: PyramidEnvironment) -> Worker:
    """Alternative worker factory for priority tasks.

    Example of how you might create multiple workers with different configurations.
    """
    logger.info("Creating priority worker")

    # Get Temporal client from registry
    temporal_client = env.registry.get("temporal_client")

    if not temporal_client:
        raise RuntimeError("Temporal client not found in registry. Make sure pyramid-temporal is properly configured.")

    worker = Worker(
        temporal_client,
        env,
        task_queue="priority-queue",  # Different task queue
        workflows=[ExampleWorkflow],
        activities=[example_activity],
    )

    logger.info("Priority worker created successfully")
    return worker
