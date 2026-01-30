"""Temporal workflows and activities for testing pyramid-temporal integration."""

import logging
import threading
from datetime import timedelta
from typing import Optional

from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

from tests.app.models import User

logger = logging.getLogger(__name__)


@activity.defn
async def enrich_user_activity(user_id: int, db_session_info: Optional[dict] = None) -> bool:
    """Activity that enriches a user.

    This activity runs with pyramid_temporal transaction management,
    so transactions are automatically handled.

    Args:
        user_id: ID of the user to enrich
        db_session_info: Database session information (for testing)

    Returns:
        bool: True if enrichment was successful

    Raises:
        ApplicationError: If user not found or enrichment fails
    """
    logger.info("Starting enrichment for user_id: %s", user_id)

    # Get database session automatically provided by pyramid_temporal
    # This is injected by our interceptor via thread-local storage
    session = getattr(threading.current_thread(), "pyramid_temporal_session", None)
    if not session:
        raise ApplicationError("Database session not available - pyramid_temporal interceptor may not be configured")

    # Log session ID for tracking
    logger.info("ACTIVITY: Using session ID: %s", id(session))

    # Find the user
    user = session.query(User).filter(User.id == user_id).first()
    if not user:
        raise ApplicationError(f"User with id {user_id} not found")

    # Perform enrichment - simply set enriched=True
    logger.info("Enriching user: %s (current enriched: %s)", user.name, user.enriched)
    user.enriched = True
    logger.info("Set user.enriched = True for user: %s", user.name)

    # Flush changes to the database within the transaction
    session.flush()
    logger.info("Flushed changes to database")

    # The transaction will be automatically committed by pyramid_temporal
    # when this activity completes successfully

    logger.info("Successfully enriched user_id: %s", user_id)
    return True


@workflow.defn(sandboxed=False)
class UserEnrichmentWorkflow:
    """Workflow for enriching user data."""

    @workflow.run
    async def run(self, user_id: int) -> bool:
        """Run the user enrichment workflow.

        Args:
            user_id: ID of the user to enrich

        Returns:
            bool: True if enrichment was successful
        """
        logger.info("Starting user enrichment workflow for user_id: %s", user_id)

        # Execute the enrichment activity with pyramid_temporal transaction management
        result = await workflow.execute_activity(
            enrich_user_activity,
            user_id,
            schedule_to_close_timeout=timedelta(seconds=60),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(initial_interval=timedelta(seconds=1), maximum_attempts=3),
        )

        logger.info("User enrichment workflow completed for user_id: %s", user_id)
        return result
