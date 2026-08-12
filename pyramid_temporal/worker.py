"""Pyramid-aware Temporal Worker.

This module provides a custom Worker class that binds pyramid-temporal
activities to the Pyramid environment, and gives sync activities the thread pool
Temporal needs to run them.
"""

import inspect
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Optional, Sequence

from temporalio.client import Client
from temporalio.worker import Worker as TemporalWorker

from .activity import PyramidActivity, is_pyramid_activity
from .environment import PyramidEnvironment

if TYPE_CHECKING:
    from temporalio.worker import Interceptor

logger = logging.getLogger(__name__)

# Temporal defaults to 100 activity slots when max_concurrent_activities is not
# given, so a thread per slot lets every concurrent execution run.
DEFAULT_ACTIVITY_SLOTS = 100

ACTIVITY_THREAD_NAME_PREFIX = "pyramid-temporal-activity"


def _is_async_activity(activity: Any) -> bool:
    """Report whether Temporal will treat this activity as async.

    Mirrors Temporal's own detection, which also accepts a callable instance
    whose ``__call__`` is a coroutine function.
    """
    if inspect.iscoroutinefunction(activity):
        return True
    return callable(activity) and inspect.iscoroutinefunction(type(activity).__call__)


class Worker:
    """Pyramid-aware Temporal Worker.

    This worker wraps the standard Temporal Worker and binds pyramid-temporal
    activities to the Pyramid environment. Each activity execution gets its own
    Pyramid request and its own transaction, so ``max_concurrent_activities``
    greater than 1 is safe.

    Activities written as plain ``def`` functions run in Temporal's activity
    executor. The worker creates a thread pool for them unless the caller passes
    its own ``activity_executor``.

    Example:
        from pyramid.paster import bootstrap
        from pyramid_temporal import Worker, activity, PyramidEnvironment

        @activity.defn
        async def my_activity(context: ActivityContext, user_id: int) -> bool:
            session = context.request.dbsession
            # ... do work ...
            return True

        # Create environment from bootstrap
        env = PyramidEnvironment.from_bootstrap(bootstrap('development.ini'))

        worker = Worker(
            client,
            env,
            task_queue="my-queue",
            activities=[my_activity],
            workflows=[MyWorkflow],
            max_concurrent_activities=10,
        )

        # Run the worker
        await worker.run()
    """

    def __init__(
        self,
        client: Client,
        env: PyramidEnvironment,
        *,
        task_queue: str,
        activities: Sequence[Any] = (),
        workflows: Sequence[type] = (),
        interceptors: Sequence["Interceptor"] = (),
        **kwargs: Any,
    ) -> None:
        """Initialize the Pyramid-aware worker.

        Args:
            client: Temporal client instance
            env: PyramidEnvironment instance (from bootstrap)
            task_queue: Name of the task queue to poll
            activities: List of activities (both pyramid-temporal and plain Temporal)
            workflows: List of workflow classes
            interceptors: Interceptors to include
            **kwargs: Additional arguments passed to Temporal Worker
        """
        self._client = client
        self._env = env
        self._task_queue = task_queue
        self._workflows = workflows
        self._interceptors = list(interceptors)
        self._extra_kwargs = kwargs

        # Bind pyramid activities to the environment and pass others through
        self._bound_activities = self._bind_activities(activities)

        # Sync activities need an executor, and the worker owns the one it creates
        self._owned_activity_executor = self._create_activity_executor()

        # Create the underlying Temporal worker
        self._worker = self._create_worker()

        logger.info(
            "Created Pyramid Worker for task queue '%s' with %d activities and %d workflows",
            task_queue,
            len(self._bound_activities),
            len(workflows),
        )

    def _bind_activities(self, activities: Sequence[Any]) -> list:
        """Bind pyramid-temporal activities to the environment, pass through others.

        Args:
            activities: List of activities (mixed pyramid and plain)

        Returns:
            List of bound/processed activities
        """
        bound = []
        for act in activities:
            if is_pyramid_activity(act):
                pyramid_act: PyramidActivity = act
                bound_act = pyramid_act.bind(self._env)
                logger.debug(
                    "Bound pyramid activity: %s (%s)",
                    pyramid_act.name,
                    "async" if pyramid_act.is_async else "sync",
                )
                bound.append(bound_act)
            else:
                # Pass through plain Temporal activity
                logger.debug("Passing through plain activity: %s", getattr(act, "__name__", act))
                bound.append(act)
        return bound

    def _create_activity_executor(self) -> Optional[ThreadPoolExecutor]:
        """Create the executor Temporal requires for sync activities.

        Temporal refuses to register a non-async activity without an
        ``activity_executor``, so the worker provides one. Callers that pass
        their own executor keep full control and own its lifetime.

        Returns:
            The created executor, or None when none is needed or wanted
        """
        if "activity_executor" in self._extra_kwargs:
            return None

        if all(_is_async_activity(act) for act in self._bound_activities):
            return None

        max_workers = self._extra_kwargs.get("max_concurrent_activities") or DEFAULT_ACTIVITY_SLOTS
        logger.info("Creating activity executor with %d threads for sync activities", max_workers)
        return ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=ACTIVITY_THREAD_NAME_PREFIX)

    def _activity_executor_kwargs(self) -> dict:
        """Return the executor keyword argument, when the worker created one."""
        if self._owned_activity_executor is None:
            return {}
        return {"activity_executor": self._owned_activity_executor}

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
            **self._activity_executor_kwargs(),
            **self._extra_kwargs,
        )

    def _shutdown_activity_executor(self) -> None:
        """Shut down the executor the worker created, if any."""
        if self._owned_activity_executor is not None:
            self._owned_activity_executor.shutdown(wait=True)
            logger.debug("Activity executor shut down")

    @property
    def env(self) -> PyramidEnvironment:
        """Get the Pyramid environment."""
        return self._env

    @property
    def task_queue(self) -> str:
        """Get the task queue name."""
        return self._task_queue

    @property
    def activity_executor(self) -> Optional[ThreadPoolExecutor]:
        """Get the activity executor the worker created for sync activities."""
        return self._owned_activity_executor

    async def run(self) -> None:
        """Run the worker until shutdown is requested.

        This is the main entry point for running the worker.
        It will poll the task queue and execute activities/workflows.
        """
        logger.info("Starting Pyramid Worker on task queue '%s'", self._task_queue)
        try:
            await self._worker.run()
        finally:
            self._shutdown_activity_executor()

    async def __aenter__(self) -> "Worker":
        """Async context manager entry."""
        await self._worker.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        try:
            await self._worker.__aexit__(*args)
        finally:
            self._shutdown_activity_executor()
