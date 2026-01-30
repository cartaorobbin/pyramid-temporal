"""Activity context for Pyramid integration.

This module provides context objects that give Temporal activities
access to Pyramid registry and request-like functionality.
"""

import logging
from typing import TYPE_CHECKING, Any, Callable, Optional

import transaction
import zope.sqlalchemy

if TYPE_CHECKING:
    from pyramid.registry import Registry
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ActivityRequest:
    """Request-like object for Temporal activities.

    This provides a familiar interface similar to Pyramid's Request object,
    giving activities access to database sessions, transaction management,
    and registry settings.

    A new ActivityRequest is created for each activity execution,
    similar to how Pyramid creates a new Request for each HTTP request.
    """

    def __init__(
        self,
        registry: "Registry",
        dbsession: "Session",
        tm: Any,
    ) -> None:
        """Initialize the activity request.

        Args:
            registry: Pyramid registry instance
            dbsession: SQLAlchemy session for this activity
            tm: Transaction manager instance
        """
        self._registry = registry
        self._dbsession = dbsession
        self._tm = tm

    @property
    def registry(self) -> "Registry":
        """Get the Pyramid registry."""
        return self._registry

    @property
    def dbsession(self) -> "Session":
        """Get the database session for this activity."""
        return self._dbsession

    @property
    def tm(self) -> Any:
        """Get the transaction manager."""
        return self._tm

    @property
    def settings(self) -> dict:
        """Get application settings (shortcut to registry.settings)."""
        return self._registry.settings


class ActivityContext:
    """Context object providing Pyramid integration for Temporal activities.

    This is the main context object passed to pyramid-temporal activities.
    It provides access to the Pyramid registry and creates request-like
    objects for each activity execution.

    Example:
        @activity.defn
        async def my_activity(context: ActivityContext, user_id: int) -> bool:
            session = context.request.dbsession
            user = session.query(User).get(user_id)
            return user is not None
    """

    def __init__(
        self,
        registry: "Registry",
        dbsession_factory: Optional[Callable[[], "Session"]] = None,
        transaction_manager: Optional[Any] = None,
    ) -> None:
        """Initialize the activity context.

        Args:
            registry: Pyramid registry instance
            dbsession_factory: Optional factory function to create database sessions.
                              If not provided, will try to get from registry.
            transaction_manager: Optional transaction manager. If not provided,
                                uses the global transaction.manager.
        """
        self._registry = registry
        self._dbsession_factory = dbsession_factory
        self._transaction_manager = transaction_manager
        self._request: Optional[ActivityRequest] = None

    @property
    def registry(self) -> "Registry":
        """Get the Pyramid registry."""
        return self._registry

    @property
    def settings(self) -> dict:
        """Get application settings (shortcut to registry.settings)."""
        return self._registry.settings

    @property
    def request(self) -> ActivityRequest:
        """Get the current activity request.

        Note: This should only be accessed during activity execution,
        after create_request() has been called by the interceptor.

        Raises:
            RuntimeError: If accessed outside of activity execution
        """
        if self._request is None:
            raise RuntimeError(
                "ActivityContext.request accessed outside of activity execution. "
                "The request is only available during activity execution."
            )
        return self._request

    def create_request(self) -> ActivityRequest:
        """Create a new ActivityRequest for an activity execution.

        This is called by the interceptor at the start of each activity.
        It creates a fresh database session and transaction for the activity.

        Returns:
            A new ActivityRequest instance
        """
        # Get or create transaction manager
        tm = self._transaction_manager or transaction.TransactionManager(explicit=True)

        # Get session factory
        session_factory = self._dbsession_factory
        if session_factory is None:
            session_factory = self._registry.get("dbsession_factory")

        if session_factory is None:
            raise RuntimeError(
                "No database session factory configured. "
                "Either pass dbsession_factory to ActivityContext or "
                "register 'dbsession_factory' in the Pyramid registry."
            )

        # Create session and register with transaction manager
        dbsession = session_factory()
        zope.sqlalchemy.register(dbsession, transaction_manager=tm)

        # Create and store the request
        self._request = ActivityRequest(
            registry=self._registry,
            dbsession=dbsession,
            tm=tm,
        )

        logger.debug("Created ActivityRequest with session id: %s", id(dbsession))
        return self._request

    def close_request(self) -> None:
        """Close the current activity request and clean up resources.

        This is called by the interceptor after activity execution completes.
        """
        if self._request is not None:
            try:
                # Close the database session
                self._request.dbsession.close()
                logger.debug("Closed ActivityRequest session")
            except Exception as e:
                logger.warning("Error closing ActivityRequest session: %s", e)
            finally:
                self._request = None
