"""Pyramid-aware Temporal activity decorator.

This module provides a custom activity decorator that enables
dependency injection of Pyramid context into Temporal activities.
"""

import functools
import inspect
import logging
from typing import Any, Callable, List, Optional, Tuple, TypeVar

from temporalio import activity as temporal_activity
from temporalio import common as temporal_common

from .context import ActivityContext
from .environment import PyramidEnvironment
from .execution import activity_execution

logger = logging.getLogger(__name__)

# Type variable for activity functions
F = TypeVar("F", bound=Callable[..., Any])

# Marker attribute to identify pyramid-temporal activities
PYRAMID_ACTIVITY_MARKER = "_pyramid_temporal_activity"

# Where Temporal looks for an activity definition. Spelled as a constant because
# writing the dunder name inside a class body would mangle it.
TEMPORAL_ACTIVITY_DEFINITION = "__temporal_activity_definition"


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

    Workflow code references the decorated activity itself, and Temporal reads
    the registered name from it:

        await workflow.execute_activity(
            my_activity, user_id, start_to_close_timeout=timedelta(seconds=30)
        )

    Args:
        fn: The activity function (when used without parentheses)
        name: Optional custom name for the activity. Defaults to function name.
        no_thread_cancel_exception: Whether Temporal should skip raising the
            cancellation exception in the activity thread. Sync activities only.

    Returns:
        A decorated activity that the Worker binds to its Pyramid environment,
        and that workflow code can pass to ``workflow.execute_activity``.

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

    The wrapper is what workflow code references, so it carries a Temporal
    activity definition and is callable: ``workflow.execute_activity(my_activity,
    ...)`` reads the registered name from that definition. What actually runs is
    the bound wrapper ``bind`` gives the Worker, and both carry the same name.
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

        # Let workflow code reference this activity instead of its name
        setattr(self, TEMPORAL_ACTIVITY_DEFINITION, self._temporal_definition())

    def _temporal_definition(self) -> temporal_activity._Definition:
        """Build the definition Temporal reads when a workflow references this.

        The types are passed explicitly rather than left to Temporal's own
        inference for two reasons: the context argument belongs to the binding
        and never travels over the wire, so it must not appear in ``arg_types``;
        and inference on a callable instance would look at ``__call__`` and lose
        the declared return type, which is what converts an activity result back
        into the type the body declared.
        """
        arg_types, ret_type = self._type_hints()
        self._check_context_parameter(arg_types)

        return temporal_activity._Definition(
            name=self._name,
            fn=self._fn,
            is_async=self.is_async,
            no_thread_cancel_exception=self._no_thread_cancel_exception,
            arg_types=None if arg_types is None else arg_types[1:],
            ret_type=ret_type,
        )

    def _type_hints(self) -> Tuple[Optional[List[type]], Optional[type]]:
        """Resolve the body's annotations, the way Temporal resolves an activity's.

        Raises:
            TypeError: If an annotation cannot be resolved, which is what a type
                imported only under ``TYPE_CHECKING`` leaves behind
        """
        try:
            return temporal_common._type_hints_from_func(self._fn)
        except NameError as error:
            raise TypeError(
                f"Activity '{self._name}' has an annotation that cannot be resolved: {error}. "
                "Temporal reads these to convert arguments and results, so every type an "
                "activity annotates must be importable at runtime, not only under TYPE_CHECKING."
            ) from error

    def _check_context_parameter(self, arg_types: Optional[List[type]]) -> None:
        """Refuse a body that cannot receive the injected context.

        Every execution calls the body with its context first, and the workflow
        facing definition describes only the arguments that follow it. A body
        without that parameter breaks both quietly: the definition would claim
        one argument fewer than the activity takes, and the mistake would
        surface as an activity failure rather than here, where it was made.

        Raises:
            TypeError: If the first parameter cannot be an ActivityContext
        """
        positional = {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.VAR_POSITIONAL,
        }
        parameters = inspect.signature(self._fn).parameters.values()

        if not any(param.kind in positional for param in parameters):
            raise TypeError(
                f"Activity '{self._name}' takes no positional argument, so it cannot "
                "receive an ActivityContext. Declare it as the first parameter."
            )

        # A first parameter annotated with nothing, or with Any, claims nothing to
        # contradict. Any needs saying explicitly because it became a class in 3.11,
        # and the check would otherwise refuse it there and accept it on 3.10.
        declared = arg_types[0] if arg_types else None
        if declared is None or declared is Any:
            return

        if isinstance(declared, type) and not issubclass(declared, ActivityContext):
            raise TypeError(
                f"Activity '{self._name}' declares {declared.__name__} as its first "
                "parameter, which must be an ActivityContext."
            )

    def __call__(self, context: ActivityContext, *args: Any, **kwargs: Any) -> Any:
        """Run the activity body inside an execution that already exists.

        This is how an activity body is exercised as a plain function, given a
        context from ``activity_execution``. Async bodies come back as their
        coroutine, for the caller to await.

        Raises:
            TypeError: If the first argument is not an ActivityContext, which
                means nothing bound the activity to a Pyramid environment.
        """
        if not isinstance(context, ActivityContext):
            raise TypeError(
                f"Activity '{self._name}' takes an ActivityContext as its first argument, "
                f"got {type(context).__name__}. Register it with pyramid_temporal.Worker, "
                "which binds the Pyramid environment, not with temporalio.worker.Worker."
            )

        return self._fn(context, *args, **kwargs)

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
