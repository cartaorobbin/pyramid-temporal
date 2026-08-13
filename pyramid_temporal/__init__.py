"""Pyramid-Temporal integration library.

This package provides automatic transaction management for Temporal activities
using pyramid_tm, similar to how it works for web requests.

Main components:
- Worker: Pyramid-aware Temporal Worker with automatic context binding
- PyramidEnvironment: Wrapper for Pyramid bootstrap environment
- activity: Decorator module for defining pyramid-temporal activities
- ActivityContext: Context object providing real Pyramid requests to activities

Activities receive real Pyramid Request objects (via Pyramid's request factory),
so all request methods configured via add_request_method work automatically
(dbsession, tm, etc.).

Each activity execution owns its request and its transaction, so activities can
run concurrently. Activities may be written as ``async def`` or as plain ``def``;
sync ones run in Temporal's activity executor, which keeps a blocking body off
the worker's event loop.

Example:
    from pyramid.paster import bootstrap
    from pyramid_temporal import Worker, activity, ActivityContext, PyramidEnvironment

    @activity.defn
    async def enrich_user(context: ActivityContext, user_id: int) -> bool:
        # Real Pyramid request with all configured methods
        session = context.request.dbsession
        user = session.query(User).get(user_id)
        user.enriched = True
        return True

    # In worker setup:
    env = PyramidEnvironment.from_bootstrap(bootstrap('development.ini'))
    worker = Worker(
        client,
        env,
        task_queue="my-queue",
        activities=[enrich_user],
        workflows=[MyWorkflow],
    )
    await worker.run()
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Optional, Tuple

from temporalio.client import Client

if TYPE_CHECKING:
    from pyramid.config import Configurator
    from pyramid.request import Request

__version__ = "0.1.1"

# Main public API
# Create an 'activity' module-like namespace for @activity.defn syntax
from . import activity
from .activity import PyramidActivity, defn, is_pyramid_activity
from .client import signal_workflow, start_workflow
from .context import ActivityContext
from .environment import PyramidEnvironment
from .execution import activity_execution
from .worker import Worker

__all__ = [
    # Main classes
    "Worker",
    "PyramidEnvironment",
    "ActivityContext",
    # Activity decorator
    "activity",
    "defn",
    "PyramidActivity",
    "is_pyramid_activity",
    # Execution scope (one request and one transaction per activity execution)
    "activity_execution",
    # Synchronous client helpers (request-free, e.g. for CLIs)
    "start_workflow",
    "signal_workflow",
    # Pyramid integration
    "includeme",
]

logger = logging.getLogger(__name__)


def includeme(config: "Configurator") -> None:
    """Pyramid configuration include function.

    This function can be called via config.include('pyramid_temporal')
    to register pyramid-temporal with a Pyramid application.

    Configuration settings:
    - pyramid_temporal.temporal_host: Temporal server host (default: localhost:7233)
    - pyramid_temporal.temporal_namespace: Temporal namespace (default: default).
      The alias pyramid_temporal.namespace is also accepted and takes precedence.
    - pyramid_temporal.task_queue: Default task queue for started workflows (default: default)
    - pyramid_temporal.log_level: Logging level (default: INFO)
    - pyramid_temporal.auto_connect: Auto-connect to Temporal on startup (default: True)

    Request methods registered:
    - request.temporal_client: The connected async Temporal client (or None).
    - request.temporal_start_workflow(workflow_run, arg, *, id, task_queue=None) -> run_id
    - request.temporal_signal_workflow(workflow_id, run_id, signal, *args) -> None

    Args:
        config: Pyramid configurator instance

    Example:
        ```python
        from pyramid.config import Configurator

        def main():
            config = Configurator()
            config.include('pyramid_temporal')

            # Optional: Configure Temporal connection
            config.registry.settings['pyramid_temporal.temporal_host'] = 'localhost:7233'

            # ... rest of configuration
        ```
    """
    logger.info("Including pyramid-temporal configuration")

    # Get settings
    settings = config.get_settings()

    # Set default settings for pyramid-temporal if they don't exist
    if "pyramid_temporal.log_level" not in settings:
        settings["pyramid_temporal.log_level"] = "INFO"

    if "pyramid_temporal.temporal_host" not in settings:
        settings["pyramid_temporal.temporal_host"] = "localhost:7233"

    if "pyramid_temporal.temporal_namespace" not in settings:
        settings["pyramid_temporal.temporal_namespace"] = "default"

    if "pyramid_temporal.task_queue" not in settings:
        settings["pyramid_temporal.task_queue"] = "default"

    if "pyramid_temporal.auto_connect" not in settings:
        settings["pyramid_temporal.auto_connect"] = "true"

    # Configure logging level
    log_level = settings.get("pyramid_temporal.log_level", "INFO").upper()
    pyramid_temporal_logger = logging.getLogger("pyramid_temporal")
    pyramid_temporal_logger.setLevel(getattr(logging, log_level, logging.INFO))

    # pyramid-temporal configuration is now complete

    # Setup Temporal client if auto_connect is enabled
    auto_connect = settings.get("pyramid_temporal.auto_connect", "true").lower() == "true"

    if auto_connect:
        _setup_temporal_client(config, settings)

    # Add request method to get Temporal client
    config.add_request_method(_get_temporal_client, "temporal_client", reify=True)

    # Add request methods to start/signal workflows from synchronous code
    config.add_request_method(temporal_start_workflow, "temporal_start_workflow")
    config.add_request_method(temporal_signal_workflow, "temporal_signal_workflow")

    logger.info("pyramid-temporal configuration complete")


def _event_loop_is_running() -> bool:
    """Return True if called from within a running asyncio event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


def _setup_temporal_client(config: "Configurator", settings: dict) -> None:
    """Setup Temporal client and register it in the registry."""

    temporal_host = settings.get("pyramid_temporal.temporal_host", "localhost:7233")
    temporal_namespace = settings.get("pyramid_temporal.temporal_namespace", "default")

    # Connecting needs a synchronous context. If we are already inside a running
    # event loop we cannot block on it, so defer and let the client be created
    # on demand instead.
    if _event_loop_is_running():
        logger.warning("Event loop already running, Temporal client will be created on-demand")
        config.registry["temporal_client"] = None
        return

    logger.debug("No running event loop; connecting to Temporal synchronously")

    try:
        logger.info(
            "Connecting to Temporal server at: %s (namespace=%s)",
            temporal_host,
            temporal_namespace,
        )

        # asyncio.run manages its own event loop, so there is no shared/closed
        # loop to leak and the connect coroutine is always awaited.
        temporal_client = asyncio.run(Client.connect(temporal_host, namespace=temporal_namespace))

        # Register client in registry
        config.registry["temporal_client"] = temporal_client
        config.registry.settings["temporal_client"] = temporal_client

        logger.info("Temporal client connected and registered")

    except Exception as e:
        logger.warning("Failed to connect to Temporal server: %s", e)
        # Register None so the app can still start
        config.registry["temporal_client"] = None


def _get_temporal_client(request: "Request") -> Optional[Client]:
    """Get Temporal client from request registry."""
    return request.registry.get("temporal_client")


def _client_settings(request: "Request") -> Tuple[str, str, str]:
    """Resolve (host, namespace, task_queue) from settings.

    The namespace accepts two keys for compatibility: the canonical
    ``pyramid_temporal.temporal_namespace`` and the alias
    ``pyramid_temporal.namespace`` (which takes precedence when set).
    """
    settings = request.registry.settings
    host = settings.get("pyramid_temporal.temporal_host", "localhost:7233")
    namespace = settings.get("pyramid_temporal.namespace") or settings.get(
        "pyramid_temporal.temporal_namespace", "default"
    )
    task_queue = settings.get("pyramid_temporal.task_queue", "default")
    return host, namespace, task_queue


def temporal_start_workflow(
    request: "Request",
    workflow_run: Any,
    arg: Any,
    *,
    id: str,  # noqa: A002 - mirrors temporalio's start_workflow(id=...) API
    task_queue: Optional[str] = None,
) -> str:
    """Start a Temporal workflow using connection settings from the registry.

    The task queue defaults to the ``pyramid_temporal.task_queue`` setting, so callers
    can omit it. Pass ``task_queue`` to override the configured queue for a single call.
    Returns the started workflow ``run_id``.
    """
    host, namespace, default_queue = _client_settings(request)
    return start_workflow(
        temporal_host=host,
        namespace=namespace,
        task_queue=task_queue or default_queue,
        workflow_run=workflow_run,
        arg=arg,
        id=id,
    )


def temporal_signal_workflow(
    request: "Request",
    workflow_id: str,
    run_id: str,
    signal: str,
    *args: Any,
) -> None:
    """Signal a running Temporal workflow using registry connection settings."""
    host, namespace, _ = _client_settings(request)
    signal_workflow(
        temporal_host=host,
        namespace=namespace,
        workflow_id=workflow_id,
        run_id=run_id,
        signal=signal,
        args=args,
    )
