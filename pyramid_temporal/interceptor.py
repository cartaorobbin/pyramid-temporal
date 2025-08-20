"""Temporal activity interceptor for automatic transaction management."""

import logging
import threading
from typing import Any, Optional

from temporalio import activity
from temporalio.worker import ActivityInboundInterceptor, Interceptor

from .transaction_manager import is_transaction_active, safe_commit, safe_abort

logger = logging.getLogger(__name__)


class TransactionalActivityInterceptor(ActivityInboundInterceptor):
    """Activity interceptor that provides automatic transaction management.
    
    This interceptor hooks into the Temporal activity execution lifecycle
    to automatically manage transactions using the configured transaction manager.
    """

    def __init__(
        self,
        next_interceptor: ActivityInboundInterceptor,
        transaction_manager: Optional[object] = None,
        db_session_factory: Optional[Any] = None,
    ) -> None:
        """Initialize the interceptor.

        Args:
            next_interceptor: The next interceptor in the chain
            transaction_manager: zope.transaction manager instance
            db_session_factory: Database session factory for creating sessions
        """
        super().__init__(next_interceptor)
        self._transaction_manager = transaction_manager
        self._db_session_factory = db_session_factory

    async def execute_activity(self, input: Any) -> Any:
        """Execute activity with automatic transaction management and session injection.

        This method wraps the activity execution with transaction management:
        1. Creates a database session using the worker's session maker
        2. Begins a transaction before executing the activity
        3. Makes the session available to the activity via worker interceptor attrs
        4. Commits the transaction if the activity succeeds
        5. Aborts the transaction if the activity fails
        6. Closes the session

        Args:
            input: Activity input

        Returns:
            Activity result

        Raises:
            Exception: Any exception raised by the activity, after transaction rollback
        """
        activity_info = getattr(input, 'info', None)
        activity_name = getattr(activity_info, 'activity_type', 'unknown') if activity_info else 'unknown'
        
        logger.info("Starting activity '%s' with transaction management", activity_name)
        
        # Get database session from session factory
        if not self._db_session_factory:
            logger.error("No db_session_factory available for activity '%s'", activity_name)
            raise RuntimeError("Database session factory not configured on interceptor")
        
        # Get the session (this should return the existing session, not create a new one)
        session = self._db_session_factory()
        
        # Store session in activity context for access by the activity
        # We'll store it in a thread-local context
        threading.current_thread().pyramid_temporal_session = session
        
        # Begin transaction if not already active
        if not is_transaction_active(self._transaction_manager):
            try:
                tm = self._transaction_manager or __import__('transaction').manager
                tm.begin()
                logger.debug("Started new transaction for activity '%s'", activity_name)
            except Exception as e:
                logger.error("Failed to start transaction for activity '%s': %s", activity_name, e)
                session.close()
                raise
        else:
            logger.debug("Transaction already active, reusing existing transaction")
        
        try:
            # Execute the activity
            logger.debug("Executing activity '%s'", activity_name)
            result = await super().execute_activity(input)
            
            # Commit transaction on success
            safe_commit(self._transaction_manager)
            logger.info("Activity '%s' executed successfully, transaction committed", activity_name)
            
            return result
            
        except Exception as e:
            # Abort transaction on any exception
            logger.warning("Activity '%s' failed with exception: %s, aborting transaction", activity_name, e)
            safe_abort(self._transaction_manager)
            raise
            
        finally:
            # Clean up thread-local session (but don't close it since we don't own it)
            if hasattr(threading.current_thread(), 'pyramid_temporal_session'):
                delattr(threading.current_thread(), 'pyramid_temporal_session')


class PyramidTemporalInterceptor(Interceptor):
    """Main interceptor class for pyramid-temporal integration.
    
    This is the main entry point for integrating pyramid-temporal
    transaction management with Temporal workers.
    """

    def __init__(
        self, 
        transaction_manager: Optional[object] = None,
        db_session_factory: Optional[Any] = None
    ) -> None:
        """Initialize the interceptor.

        Args:
            transaction_manager: zope.transaction manager instance
            db_session_factory: Database session factory for creating sessions
        """
        self._transaction_manager = transaction_manager
        self._db_session_factory = db_session_factory
        logger.info("Initialized PyramidTemporalInterceptor with transaction manager: %s", 
                   type(self._transaction_manager).__name__ if self._transaction_manager else "default")

    def intercept_activity(
        self, next_interceptor: ActivityInboundInterceptor
    ) -> ActivityInboundInterceptor:
        """Intercept activity execution to add transaction management.

        Args:
            next_interceptor: The next interceptor in the chain

        Returns:
            Transactional activity interceptor
        """
        return TransactionalActivityInterceptor(
            next_interceptor, 
            self._transaction_manager, 
            self._db_session_factory
        )
