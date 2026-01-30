"""Example worker factory for use with ptemporal-worker command.

This demonstrates how to create a worker factory function that can be used
with the ptemporal-worker CLI command, using the new pyramid-temporal API.

Usage:
    ptemporal-worker examples/basic/development.ini examples.basic.worker.create_worker
"""

import logging
from datetime import timedelta

from temporalio import workflow

from pyramid_temporal import ActivityContext, Worker, activity

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
async def database_activity(context: ActivityContext, user_id: int) -> dict:
    """Example activity that uses the database session.

    This demonstrates how to use the context to access the database.
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


def create_worker(registry) -> Worker:
    """Worker factory function for ptemporal-worker command.

    This function demonstrates the new pyramid-temporal API.
    It receives a Pyramid registry and returns a configured Worker instance.

    The Worker automatically:
    - Binds pyramid-temporal activities to the context
    - Sets up transaction management
    - Creates database sessions per activity

    Args:
        registry: Pyramid registry instance with pyramid-temporal already configured

    Returns:
        Worker: Configured pyramid-temporal Worker instance
    """
    logger.info("Creating example worker with new API")

    # Get Temporal client from registry (created by pyramid-temporal includeme)
    temporal_client = registry.get("temporal_client")

    if not temporal_client:
        raise RuntimeError(
            "Temporal client not found in registry. "
            "Make sure pyramid-temporal is properly configured in your INI file "
            "and pyramid_temporal.auto_connect is set to true."
        )

    # Create worker with pyramid-temporal - context binding is automatic!
    worker = Worker(
        temporal_client,
        registry,  # Pyramid registry for context access
        task_queue="example-queue",
        workflows=[ExampleWorkflow],
        activities=[example_activity, database_activity],
        # dbsession_factory is optional - will use registry['dbsession_factory'] if available
    )

    logger.info("Example worker created successfully")
    return worker


# Alternative factory for different task queue
def create_priority_worker(registry) -> Worker:
    """Alternative worker factory for priority tasks.

    Example of how you might create multiple workers with different configurations.
    """
    logger.info("Creating priority worker")

    # Get Temporal client from registry
    temporal_client = registry.get("temporal_client")

    if not temporal_client:
        raise RuntimeError("Temporal client not found in registry. Make sure pyramid-temporal is properly configured.")

    worker = Worker(
        temporal_client,
        registry,
        task_queue="priority-queue",  # Different task queue
        workflows=[ExampleWorkflow],
        activities=[example_activity],
    )

    logger.info("Priority worker created successfully")
    return worker
