"""Pyramid-aware Temporal activity decorator.

This module provides a custom activity decorator that enables
dependency injection of Pyramid context into Temporal activities.
"""

import functools
import inspect
import logging
from typing import Any, Callable, Optional, TypeVar

from temporalio import activity as temporal_activity

from .environment import PyramidEnvironment
from .execution import activity_execution

logger = logging.getLogger(__name__)

# Type variable for activity functions
F = TypeVar("F", bound=Callable[..., Any])

# Marker attribute to identify pyramid-temporal activities
PYRAMID_ACTIVITY_MARKER = "_pyramid_temporal_activity"


def defn(
    fn: Optional[F] = None,
    *,
    name: Optional[str] = None,
    no_thread_cancel_exception: bool = False,
) -> Any:
    """Decorator to define a pyramid-temporal activity.

    This decorator marks a function as a pyramid-temporal activity that
    will receive an ActivityContext as its first argument. The context
    is automatically injected when the activity is executed via the
    pyramid-temporal Worker.

    The decorated function should have ActivityContext as its first parameter:

        @activity.defn
        async def my_activity(context: ActivityContext, user_id: int) -> bool:
            session = context.request.dbsession
            # ... do work ...
            return True

    A plain ``def`` works too, and is the better choice whenever the body
    blocks. Temporal runs sync activities in its activity executor, so a
    blocking call never occupies the worker's event loop:

        @activity.defn
        def my_blocking_activity(context: ActivityContext, user_id: int) -> bool:
            session = context.request.dbsession
            # ... blocking HTTP, gRPC, or database work ...
            return True

    Args:
        fn: The activity function (when used without parentheses)
        name: Optional custom name for the activity. Defaults to function name.
        no_thread_cancel_exception: Whether Temporal should skip raising the
            cancellation exception in the activity thread. Sync activities only.

    Returns:
        A decorated activity that the Worker binds to its Pyramid environment.

    Example:
        @activity.defn
        async def process_order(context: ActivityContext, order_id: int) -> bool:
            session = context.request.dbsession
            order = session.query(Order).get(order_id)
            # Process the order...
            return True

        # Or with custom name:
        @activity.defn(name="custom-activity-name")
        async def my_activity(context: ActivityContext, data: str) -> str:
            return data.upper()
    """

    def decorator(func: F) -> "PyramidActivity":
        activity = PyramidActivity(
            func,
            name=name,
            no_thread_cancel_exception=no_thread_cancel_exception,
        )
        return activity

    # Handle both @activity.defn and @activity.defn() syntax
    if fn is not None:
        return decorator(fn)
    return decorator


class PyramidActivity:
    """Wrapper for pyramid-temporal activities.

    This class wraps an activity function and provides the ability to bind it to
    a Pyramid environment for execution.
    """

    def __init__(
        self,
        fn: Callable[..., Any],
        name: Optional[str] = None,
        no_thread_cancel_exception: bool = False,
    ) -> None:
        """Initialize the pyramid activity wrapper.

        Args:
            fn: The original activity function
            name: Optional custom activity name
            no_thread_cancel_exception: Thread cancellation setting, sync only
        """
        self._fn = fn
        self._name = name or fn.__name__
        self._no_thread_cancel_exception = no_thread_cancel_exception

        # Copy function metadata for better debugging
        functools.update_wrapper(self, fn)

        # Mark as pyramid-temporal activity
        setattr(self, PYRAMID_ACTIVITY_MARKER, True)

    @property
    def name(self) -> str:
        """Get the activity name."""
        return self._name

    @property
    def fn(self) -> Callable[..., Any]:
        """Get the original function."""
        return self._fn

    @property
    def is_async(self) -> bool:
        """Whether the activity body is a coroutine function."""
        return inspect.iscoroutinefunction(self._fn)

    def bind(self, env: PyramidEnvironment) -> Callable[..., Any]:
        """Bind this activity to a Pyramid environment for Temporal registration.

        Every call of the returned activity is one execution, and owns its own
        ActivityContext, Pyramid request, and transaction. Nothing is shared
        between executions, so they are safe to run concurrently.

        An async activity binds to a coroutine function, which Temporal runs on
        the worker's event loop. A sync activity binds to a plain function, which
        Temporal runs in its activity executor, so a blocking body leaves the
        event loop free.

        Args:
            env: The PyramidEnvironment each execution builds its request from

        Returns:
            An activity that can be registered with a Temporal Worker
        """
        fn = self._fn
        name = self._name

        if self.is_async:

            @temporal_activity.defn(name=name)
            async def execute_async(*args: Any, **kwargs: Any) -> Any:
                """Execute one async activity execution with context injection."""
                with activity_execution(env, threadlocal_request=False) as context:
                    return await fn(context, *args, **kwargs)

            return execute_async

        @temporal_activity.defn(name=name, no_thread_cancel_exception=self._no_thread_cancel_exception)
        def execute_sync(*args: Any, **kwargs: Any) -> Any:
            """Execute one sync activity execution with context injection."""
            with activity_execution(env, threadlocal_request=True) as context:
                return fn(context, *args, **kwargs)

        return execute_sync

    def __repr__(self) -> str:
        return f"<PyramidActivity '{self._name}'>"


def is_pyramid_activity(obj: Any) -> bool:
    """Check if an object is a pyramid-temporal activity.

    Args:
        obj: Object to check

    Returns:
        True if the object is a pyramid-temporal activity
    """
    return getattr(obj, PYRAMID_ACTIVITY_MARKER, False)
