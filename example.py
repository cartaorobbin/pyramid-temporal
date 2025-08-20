#!/usr/bin/env python3
"""Example usage of pyramid-temporal.

This example demonstrates how to use pyramid-temporal to automatically
manage transactions in Temporal activities.
"""

import asyncio
import logging
from typing import Any

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker

from pyramid_temporal import PyramidTemporalInterceptor

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
            
            return result
            
        except Exception as e:
            logger.error("Workflow failed: %s", e)
            raise


async def main() -> None:
    """Main function to demonstrate the library."""
    logger.info("Starting pyramid-temporal example")
    
    # Create Temporal client
    client = await Client.connect("localhost:7233")
    
    # Create worker with pyramid-temporal interceptor
    worker = Worker(
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


if __name__ == "__main__":
    asyncio.run(main())
