"""Activity context for Pyramid integration.

This module provides context objects that give Temporal activities
access to real Pyramid requests via pyramid.scripting.prepare.
"""

import logging
from typing import TYPE_CHECKING, Optional

from pyramid.request import Request
from pyramid.scripting import prepare

from .environment import PyramidEnvironment

if TYPE_CHECKING:
    from pyramid.registry import Registry

logger = logging.getLogger(__name__)


class ActivityContext:
    """Context object providing Pyramid integration for Temporal activities.

    This is the main context object passed to pyramid-temporal activities.
    It provides access to the Pyramid environment, registry, and creates
    real Pyramid requests for each activity execution using pyramid.scripting.prepare.

    The request has all the same properties and methods as a web request,
    including any configured via add_request_method (like dbsession, tm, etc.).

    Example:
        @activity.defn
        async def my_activity(context: ActivityContext, user_id: int) -> bool:
            # Real Pyramid request with all configured methods
            session = context.request.dbsession
            user = session.query(User).get(user_id)
            return user is not None
    """

    def __init__(self, env: PyramidEnvironment) -> None:
        """Initialize the activity context.

        Args:
            env: PyramidEnvironment instance
        """
        self._env = env
        self._request: Optional[Request] = None
        self._prepare_env: Optional[dict] = None

    @property
    def env(self) -> PyramidEnvironment:
        """Get the Pyramid environment."""
        return self._env

    @property
    def registry(self) -> "Registry":
        """Get the Pyramid registry."""
        return self._env.registry

    @property
    def settings(self) -> dict:
        """Get application settings (shortcut to registry.settings)."""
        return self._env.registry.settings

    @property
    def request(self) -> Request:
        """Get the current activity request.

        This is a real Pyramid Request object with all configured
        request methods (dbsession, tm, etc.) available.

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

    def create_request(self) -> Request:
        """Create a new Pyramid Request for an activity execution.

        This is called by the interceptor at the start of each activity.
        It uses pyramid.scripting.prepare to create a real Pyramid request
        with all configured request methods and proper threadlocal setup.

        Returns:
            A real Pyramid Request instance
        """
        # Use pyramid.scripting.prepare for a real Pyramid request
        # This sets up threadlocals, applies request extensions, etc.
        self._prepare_env = prepare(registry=self._env.registry)
        self._request = self._prepare_env["request"]

        logger.debug(
            "Created Pyramid Request for activity (request id: %s)",
            id(self._request),
        )
        return self._request

    def close_request(self) -> None:
        """Close the current activity request and clean up resources.

        This is called by the interceptor after activity execution completes.
        It calls the closer from pyramid.scripting.prepare to properly
        clean up the request context and threadlocals.
        """
        if self._prepare_env is not None:
            try:
                # Call the closer from prepare() to clean up
                closer = self._prepare_env.get("closer")
                if closer is not None:
                    closer()
                logger.debug("Closed Pyramid Request context")
            except Exception as e:
                logger.warning("Error closing Pyramid Request context: %s", e)
            finally:
                self._prepare_env = None
                self._request = None
