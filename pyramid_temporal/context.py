"""Activity context for Pyramid integration.

This module provides the context object that gives a single Temporal activity
execution a real Pyramid request, built with Pyramid's request factory, request
extensions, and threadlocal context APIs.
"""

import logging
from typing import TYPE_CHECKING, Optional, Union

from pyramid.interfaces import IRequestFactory
from pyramid.request import Request, apply_request_extensions
from pyramid.threadlocal import RequestContext, manager

from .environment import PyramidEnvironment

if TYPE_CHECKING:
    from pyramid.registry import Registry

logger = logging.getLogger(__name__)


class RegistryContext:
    """Threadlocal scope that publishes the registry, but no request.

    Pyramid's threadlocal stack lives on the thread, so it cannot tell apart
    activity executions that share the worker's event loop thread. Publishing
    only the registry keeps ``get_current_registry`` correct while making every
    entry on the stack identical, so overlapping executions may begin and end in
    any order. ``get_current_request`` then reports nothing, instead of handing
    out another execution's request.
    """

    def __init__(self, registry: "Registry") -> None:
        self._registry = registry

    def begin(self) -> None:
        """Publish the registry for the current thread."""
        manager.push({"registry": self._registry, "request": None})

    def end(self) -> None:
        """Withdraw one registry entry from the current thread."""
        manager.pop()


class ActivityContext:
    """Context object providing Pyramid integration for one activity execution.

    A context belongs to a single execution. The bound activity creates one per
    invocation, so concurrent executions never share a request, and therefore
    never share a dbsession or a transaction.

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
        self._threadlocal_context: Optional[Union[RequestContext, RegistryContext]] = None

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
        """Get this execution's request.

        This is a real Pyramid Request object with all configured
        request methods (dbsession, tm, etc.) available.

        Raises:
            RuntimeError: If accessed outside of activity execution
        """
        if self._request is None:
            raise RuntimeError(
                "ActivityContext.request accessed outside of activity execution. "
                "The request is only available during activity execution."
            )
        return self._request

    def create_request(self, *, threadlocal_request: bool = True) -> Request:
        """Create the Pyramid Request for this activity execution.

        Uses Pyramid's request factory to create a real request, applies request
        extensions (add_request_method), and opens a threadlocal scope.

        Args:
            threadlocal_request: Publish the request on Pyramid's threadlocal
                stack, so ``get_current_request`` returns it. Only correct when
                the execution owns its thread, which is the case for a sync
                activity running in Temporal's activity executor. Concurrent
                async executions share the event loop thread, so they publish
                the registry alone instead.

        Returns:
            A real Pyramid Request instance

        Raises:
            RuntimeError: If this context already has a request
        """
        if self._request is not None:
            raise RuntimeError(
                "ActivityContext already has a request. A context belongs to a "
                "single activity execution and cannot be reused."
            )

        registry = self._env.registry
        request_factory = registry.queryUtility(IRequestFactory, default=Request)
        request = request_factory.blank("/")
        request.registry = registry

        if self._env.request is not None:
            request.environ.update(self._env.request.environ)

        self._threadlocal_context = RequestContext(request) if threadlocal_request else RegistryContext(registry)
        self._threadlocal_context.begin()
        apply_request_extensions(request)

        self._request = request

        logger.debug(
            "Created Pyramid Request for activity (request id: %s)",
            id(self._request),
        )
        return self._request

    def close_request(self) -> None:
        """Close this execution's request and clean up resources.

        Processes finished callbacks and tears down the threadlocal scope.
        """
        request = self._request
        threadlocal_context = self._threadlocal_context

        if request is None or threadlocal_context is None:
            return

        try:
            if request.finished_callbacks:
                request._process_finished_callbacks()
            threadlocal_context.end()
            logger.debug("Closed Pyramid Request context")
        except Exception as e:
            logger.warning("Error closing Pyramid Request context: %s", e)
        finally:
            self._threadlocal_context = None
            self._request = None
