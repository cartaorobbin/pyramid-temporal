"""Temporal workflows and activities for testing pyramid-temporal integration."""

import logging
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

from pyramid_temporal import ActivityContext, activity
from tests.app.models import User

logger = logging.getLogger(__name__)


@activity.defn
async def enrich_user_activity(context: ActivityContext, user_id: int) -> bool:
    """Activity that enriches a user using the Pyramid request session.

    The activity receives an ActivityContext, and pyramid-temporal provides a
    real Pyramid request with all configured request methods (dbsession, tm).
    The interceptor manages the transaction lifecycle around this call.

    Args:
        context: Activity context exposing the per-activity Pyramid request
        user_id: ID of the user to enrich

    Returns:
        bool: True if enrichment was successful

    Raises:
        ApplicationError: If the user is not found
    """
    logger.info("Starting enrichment for user_id: %s", user_id)

    session = context.request.dbsession
    logger.info("ACTIVITY: Using session ID: %s", id(session))

    user = session.query(User).filter(User.id == user_id).first()
    if not user:
        raise ApplicationError(f"User with id {user_id} not found")

    logger.info("Enriching user: %s (current enriched: %s)", user.name, user.enriched)
    user.enriched = True
    session.flush()
    logger.info("Flushed enrichment for user_id: %s", user_id)

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

        result = await workflow.execute_activity(
            enrich_user_activity.name,
            user_id,
            schedule_to_close_timeout=timedelta(seconds=60),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(initial_interval=timedelta(seconds=1), maximum_attempts=3),
        )

        logger.info("User enrichment workflow completed for user_id: %s", user_id)
        return result
