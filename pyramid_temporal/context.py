"""Activity context for Pyramid integration.

This module provides context objects that give Temporal activities
access to real Pyramid requests using Pyramid's request factory,
request extensions, and threadlocal context APIs.
"""

import logging
from typing import TYPE_CHECKING, Optional

from pyramid.interfaces import IRequestFactory
from pyramid.request import Request, apply_request_extensions
from pyramid.threadlocal import RequestContext

from .environment import PyramidEnvironment

if TYPE_CHECKING:
    from pyramid.registry import Registry

logger = logging.getLogger(__name__)


class ActivityContext:
    """Context object providing Pyramid integration for Temporal activities.

    This is the main context object passed to pyramid-temporal activities.
    It provides access to the Pyramid environment, registry, and creates
    real Pyramid requests for each activity execution using Pyramid's
    request factory and request extension APIs.

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
        self._request_context: Optional[RequestContext] = None

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
        It uses Pyramid's request factory to create a real request, applies
        request extensions (add_request_method), and sets up threadlocals.

        Returns:
            A real Pyramid Request instance
        """
        registry = self._env.registry
        request_factory = registry.queryUtility(IRequestFactory, default=Request)
        request = request_factory.blank("/")
        request.registry = registry

        if self._env.request is not None:
            request.environ.update(self._env.request.environ)

        self._request_context = RequestContext(request)
        self._request_context.begin()
        apply_request_extensions(request)

        self._request = request

        logger.debug(
            "Created Pyramid Request for activity (request id: %s)",
            id(self._request),
        )
        return self._request

    def close_request(self) -> None:
        """Close the current activity request and clean up resources.

        This is called by the interceptor after activity execution completes.
        It processes finished callbacks and tears down the threadlocal context.
        """
        if self._request is not None:
            try:
                if self._request.finished_callbacks:
                    self._request._process_finished_callbacks()
                self._request_context.end()
                logger.debug("Closed Pyramid Request context")
            except Exception as e:
                logger.warning("Error closing Pyramid Request context: %s", e)
            finally:
                self._request_context = None
                self._request = None
