"""Pyramid-aware Temporal activity decorator.

This module provides a custom activity decorator that enables
dependency injection of Pyramid context into Temporal activities.
"""

import functools
import logging
from typing import Any, Callable, Optional, TypeVar

from temporalio import activity as temporal_activity

from .context import ActivityContext

logger = logging.getLogger(__name__)

# Type variable for activity functions
F = TypeVar("F", bound=Callable[..., Any])

# Marker attribute to identify pyramid-temporal activities
PYRAMID_ACTIVITY_MARKER = "_pyramid_temporal_activity"


def defn(
    fn: Optional[F] = None,
    *,
    name: Optional[str] = None,
    no_thread_cancel_default: bool = False,
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

    Args:
        fn: The activity function (when used without parentheses)
        name: Optional custom name for the activity. Defaults to function name.
        no_thread_cancel_default: Whether to disable thread cancellation by default.

    Returns:
        A decorated activity that can be bound to a context via the Worker.

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
            no_thread_cancel_default=no_thread_cancel_default,
        )
        return activity

    # Handle both @activity.defn and @activity.defn() syntax
    if fn is not None:
        return decorator(fn)
    return decorator


class PyramidActivity:
    """Wrapper for pyramid-temporal activities.

    This class wraps an activity function and provides the ability to
    bind it to an ActivityContext for execution.
    """

    def __init__(
        self,
        fn: Callable[..., Any],
        name: Optional[str] = None,
        no_thread_cancel_default: bool = False,
    ) -> None:
        """Initialize the pyramid activity wrapper.

        Args:
            fn: The original activity function
            name: Optional custom activity name
            no_thread_cancel_default: Thread cancellation setting
        """
        self._fn = fn
        self._name = name or fn.__name__
        self._no_thread_cancel_default = no_thread_cancel_default

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

    def bind(self, context: ActivityContext) -> Callable[..., Any]:
        """Bind this activity to a context, returning a Temporal-compatible activity.

        This creates a wrapper class that injects the context as the first
        argument when the activity is executed.

        Args:
            context: The ActivityContext to bind to

        Returns:
            A bound activity method that can be registered with Temporal Worker
        """
        fn = self._fn
        name = self._name

        class BoundActivity:
            """Bound activity class for Temporal registration."""

            def __init__(self, ctx: ActivityContext) -> None:
                self.context = ctx

            @temporal_activity.defn(name=name)
            async def execute(self, *args: Any, **kwargs: Any) -> Any:
                """Execute the activity with context injection."""
                return await fn(self.context, *args, **kwargs)

        instance = BoundActivity(context)
        return instance.execute

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
