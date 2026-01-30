"""Temporal activity interceptor for automatic transaction management."""

import logging
from typing import TYPE_CHECKING, Any, Optional

from temporalio.worker import ActivityInboundInterceptor, Interceptor

from .transaction_manager import is_transaction_active, safe_abort, safe_commit

if TYPE_CHECKING:
    from .context import ActivityContext

logger = logging.getLogger(__name__)


class TransactionalActivityInterceptor(ActivityInboundInterceptor):
    """Activity interceptor that provides automatic transaction management.

    This interceptor hooks into the Temporal activity execution lifecycle
    to automatically manage transactions and activity context.
    """

    def __init__(
        self,
        next_interceptor: ActivityInboundInterceptor,
        context: Optional["ActivityContext"] = None,
    ) -> None:
        """Initialize the interceptor.

        Args:
            next_interceptor: The next interceptor in the chain
            context: ActivityContext for creating request objects
        """
        super().__init__(next_interceptor)
        self._context = context

    async def execute_activity(self, input: Any) -> Any:
        """Execute activity with automatic transaction management.

        This method wraps the activity execution with transaction management:
        1. Creates an ActivityRequest via the context (with db session)
        2. Begins a transaction before executing the activity
        3. Commits the transaction if the activity succeeds
        4. Aborts the transaction if the activity fails
        5. Cleans up the request/session

        Args:
            input: Activity input

        Returns:
            Activity result

        Raises:
            Exception: Any exception raised by the activity, after transaction rollback
        """
        activity_info = getattr(input, "info", None)
        activity_name = getattr(activity_info, "activity_type", "unknown") if activity_info else "unknown"

        logger.info("Starting activity '%s' with transaction management", activity_name)

        # Create request via context (includes db session)
        request = None
        tm = None

        if self._context is not None:
            try:
                request = self._context.create_request()
                tm = request.tm
                logger.debug("Created ActivityRequest for activity '%s'", activity_name)
            except Exception as e:
                logger.error("Failed to create ActivityRequest for activity '%s': %s", activity_name, e)
                raise

        # Begin transaction if we have a transaction manager
        if tm is not None and not is_transaction_active(tm):
            try:
                tm.begin()
                logger.debug("Started new transaction for activity '%s'", activity_name)
            except Exception as e:
                logger.error("Failed to start transaction for activity '%s': %s", activity_name, e)
                if self._context is not None:
                    self._context.close_request()
                raise

        try:
            # Execute the activity
            logger.debug("Executing activity '%s'", activity_name)
            result = await super().execute_activity(input)

            # Commit transaction on success
            if tm is not None:
                safe_commit(tm)
                logger.info("Activity '%s' executed successfully, transaction committed", activity_name)
            else:
                logger.info("Activity '%s' executed successfully (no transaction)", activity_name)

            return result

        except Exception as e:
            # Abort transaction on any exception
            if tm is not None:
                logger.warning("Activity '%s' failed with exception: %s, aborting transaction", activity_name, e)
                safe_abort(tm)
            else:
                logger.warning("Activity '%s' failed with exception: %s", activity_name, e)
            raise

        finally:
            # Clean up request/session
            if self._context is not None:
                self._context.close_request()
                logger.debug("Cleaned up ActivityRequest for activity '%s'", activity_name)


class PyramidTemporalInterceptor(Interceptor):
    """Main interceptor class for pyramid-temporal integration.

    This is the main entry point for integrating pyramid-temporal
    transaction management with Temporal workers.
    """

    def __init__(
        self,
        context: Optional["ActivityContext"] = None,
    ) -> None:
        """Initialize the interceptor.

        Args:
            context: ActivityContext for request/session management
        """
        self._context = context
        logger.info("Initialized PyramidTemporalInterceptor with context: %s", "yes" if context else "no")

    def intercept_activity(self, next_interceptor: ActivityInboundInterceptor) -> ActivityInboundInterceptor:
        """Intercept activity execution to add transaction management.

        Args:
            next_interceptor: The next interceptor in the chain

        Returns:
            Transactional activity interceptor
        """
        return TransactionalActivityInterceptor(
            next_interceptor,
            context=self._context,
        )
