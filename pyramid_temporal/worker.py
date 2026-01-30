"""Pyramid-aware Temporal Worker.

This module provides a custom Worker class that automatically handles
context binding for pyramid-temporal activities.
"""

import logging
from typing import TYPE_CHECKING, Any, Callable, Optional, Sequence

from temporalio.client import Client
from temporalio.worker import Worker as TemporalWorker

from .activity import PyramidActivity, is_pyramid_activity
from .context import ActivityContext
from .interceptor import PyramidTemporalInterceptor

if TYPE_CHECKING:
    from pyramid.registry import Registry
    from sqlalchemy.orm import Session
    from temporalio.worker import Interceptor

logger = logging.getLogger(__name__)


class Worker:
    """Pyramid-aware Temporal Worker.

    This worker wraps the standard Temporal Worker and provides automatic
    context binding for pyramid-temporal activities. It also includes
    transaction management via the PyramidTemporalInterceptor.

    Example:
        from pyramid_temporal import Worker, activity

        @activity.defn
        async def my_activity(context: ActivityContext, user_id: int) -> bool:
            session = context.request.dbsession
            # ... do work ...
            return True

        worker = Worker(
            client,
            registry,
            task_queue="my-queue",
            activities=[my_activity],
            workflows=[MyWorkflow],
        )

        # Run the worker
        await worker.run()
    """

    def __init__(
        self,
        client: Client,
        registry: "Registry",
        *,
        task_queue: str,
        activities: Sequence[Any] = (),
        workflows: Sequence[type] = (),
        dbsession_factory: Optional[Callable[[], "Session"]] = None,
        interceptors: Sequence["Interceptor"] = (),
        **kwargs: Any,
    ) -> None:
        """Initialize the Pyramid-aware worker.

        Args:
            client: Temporal client instance
            registry: Pyramid registry instance (required for context access)
            task_queue: Name of the task queue to poll
            activities: List of activities (both pyramid-temporal and plain Temporal)
            workflows: List of workflow classes
            dbsession_factory: Optional database session factory. If not provided,
                              will try to get 'dbsession_factory' from registry.
            interceptors: Additional interceptors to include (pyramid-temporal
                         interceptor is automatically added)
            **kwargs: Additional arguments passed to Temporal Worker
        """
        self._client = client
        self._registry = registry
        self._task_queue = task_queue
        self._dbsession_factory = dbsession_factory or registry.get("dbsession_factory")
        self._workflows = workflows
        self._extra_kwargs = kwargs

        # Create the activity context
        self._context = ActivityContext(
            registry=registry,
            dbsession_factory=self._dbsession_factory,
        )

        # Bind activities and separate pyramid vs plain
        self._bound_activities = self._bind_activities(activities)

        # Create interceptors list with our interceptor first
        self._interceptors = self._create_interceptors(interceptors)

        # Create the underlying Temporal worker
        self._worker = self._create_worker()

        logger.info(
            "Created Pyramid Worker for task queue '%s' with %d activities and %d workflows",
            task_queue,
            len(self._bound_activities),
            len(workflows),
        )

    def _bind_activities(self, activities: Sequence[Any]) -> list:
        """Bind pyramid-temporal activities to context, pass through others.

        Args:
            activities: List of activities (mixed pyramid and plain)

        Returns:
            List of bound/processed activities
        """
        bound = []
        for act in activities:
            if is_pyramid_activity(act):
                # Bind pyramid-temporal activity to context
                pyramid_act: PyramidActivity = act
                bound_act = pyramid_act.bind(self._context)
                logger.debug("Bound pyramid activity: %s", pyramid_act.name)
                bound.append(bound_act)
            else:
                # Pass through plain Temporal activity
                logger.debug("Passing through plain activity: %s", getattr(act, "__name__", act))
                bound.append(act)
        return bound

    def _create_interceptors(self, extra_interceptors: Sequence["Interceptor"]) -> list["Interceptor"]:
        """Create the interceptors list with pyramid-temporal interceptor.

        Args:
            extra_interceptors: Additional interceptors from user

        Returns:
            List of interceptors with PyramidTemporalInterceptor included
        """
        # Create our interceptor with context reference
        pyramid_interceptor = PyramidTemporalInterceptor(
            context=self._context,
        )

        # Our interceptor first, then user's interceptors
        return [pyramid_interceptor, *extra_interceptors]

    def _create_worker(self) -> TemporalWorker:
        """Create the underlying Temporal worker.

        Returns:
            Configured Temporal Worker instance
        """
        return TemporalWorker(
            self._client,
            task_queue=self._task_queue,
            activities=self._bound_activities,
            workflows=list(self._workflows),
            interceptors=self._interceptors,
            **self._extra_kwargs,
        )

    @property
    def context(self) -> ActivityContext:
        """Get the activity context."""
        return self._context

    @property
    def task_queue(self) -> str:
        """Get the task queue name."""
        return self._task_queue

    async def run(self) -> None:
        """Run the worker until shutdown is requested.

        This is the main entry point for running the worker.
        It will poll the task queue and execute activities/workflows.
        """
        logger.info("Starting Pyramid Worker on task queue '%s'", self._task_queue)
        await self._worker.run()

    async def __aenter__(self) -> "Worker":
        """Async context manager entry."""
        await self._worker.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self._worker.__aexit__(*args)
