"""Example worker factory for use with ptemporal-worker command.

This demonstrates how to create a worker factory function that can be used
with the ptemporal-worker CLI command.

Usage:
    ptemporal-worker examples/basic/development.ini examples.basic.worker.create_worker
"""

import logging
from datetime import timedelta
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker
from pyramid_temporal import PyramidTemporalInterceptor

logger = logging.getLogger(__name__)


@activity.defn
async def example_activity(message: str) -> str:
    """Example activity that demonstrates transaction management.
    
    This activity will automatically have transaction management via
    pyramid-temporal interceptor.
    """
    logger.info("Processing message: %s", message)
    # Your business logic here - database operations will be transactional
    return f"Processed: {message}"


@workflow.defn(sandboxed=False)
class ExampleWorkflow:
    """Example workflow."""
    
    @workflow.run
    async def run(self, message: str) -> str:
        """Run the example workflow."""
        return await workflow.execute_activity(
            example_activity,
            message,
            schedule_to_close_timeout=timedelta(seconds=60)
        )


def create_worker(registry) -> Worker:
    """Worker factory function for ptemporal-worker command.
    
    This function demonstrates the expected signature for worker factory functions.
    It receives a Pyramid registry and returns a configured Worker instance.
    
    Args:
        registry: Pyramid registry instance with pyramid-temporal already configured
        
    Returns:
        Worker: Configured Temporal worker instance
    """
    logger.info("Creating example worker")
    
    # Get Temporal client from registry (created by pyramid-temporal includeme)
    temporal_client = registry.get('temporal_client')
    
    if not temporal_client:
        raise RuntimeError(
            "Temporal client not found in registry. "
            "Make sure pyramid-temporal is properly configured in your INI file "
            "and pyramid_temporal.auto_connect is set to true."
        )
    
    # Create worker with pyramid-temporal transaction management
    worker = Worker(
        temporal_client,
        task_queue="example-queue",
        workflows=[ExampleWorkflow],
        activities=[example_activity],
        interceptors=[PyramidTemporalInterceptor()],  # Automatic transaction management
    )
    
    logger.info("Example worker created successfully")
    return worker


# Alternative factory for different task queue
def create_priority_worker(registry) -> Worker:
    """Alternative worker factory for priority tasks.
    
    Example of how you might create multiple workers with different configurations.
    """
    logger.info("Creating priority worker")
    
    # Get Temporal client from registry (created by pyramid-temporal includeme)
    temporal_client = registry.get('temporal_client')
    
    if not temporal_client:
        raise RuntimeError(
            "Temporal client not found in registry. "
            "Make sure pyramid-temporal is properly configured."
        )
    
    worker = Worker(
        temporal_client,
        task_queue="priority-queue",  # Different task queue
        workflows=[ExampleWorkflow],
        activities=[example_activity],
        interceptors=[PyramidTemporalInterceptor()],
    )
    
    logger.info("Priority worker created successfully")
    return worker
