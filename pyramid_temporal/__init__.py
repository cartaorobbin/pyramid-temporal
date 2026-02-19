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
from typing import TYPE_CHECKING

from temporalio.client import Client

if TYPE_CHECKING:
    from pyramid.config import Configurator

__version__ = "0.0.1"

# Main public API
# Create an 'activity' module-like namespace for @activity.defn syntax
from . import activity
from .activity import PyramidActivity, defn, is_pyramid_activity
from .context import ActivityContext
from .environment import PyramidEnvironment
from .interceptor import PyramidTemporalInterceptor
from .worker import Worker

__all__ = [
    # Main classes
    "Worker",
    "PyramidEnvironment",
    "ActivityContext",
    "PyramidTemporalInterceptor",
    # Activity decorator
    "activity",
    "defn",
    "PyramidActivity",
    "is_pyramid_activity",
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
    - pyramid_temporal.log_level: Logging level (default: INFO)
    - pyramid_temporal.auto_connect: Auto-connect to Temporal on startup (default: True)

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

    logger.info("pyramid-temporal configuration complete")


def _setup_temporal_client(config: "Configurator", settings: dict) -> None:
    """Setup Temporal client and register it in the registry."""

    temporal_host = settings.get("pyramid_temporal.temporal_host", "localhost:7233")

    try:
        logger.info("Connecting to Temporal server at: %s", temporal_host)

        # Create async function to connect to Temporal
        async def create_temporal_client():
            return await Client.connect(temporal_host)

        # Create new event loop if needed and connect
        try:
            # Try to get existing loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, we'll defer connection
                logger.warning("Event loop already running, Temporal client will be created on-demand")
                config.registry["temporal_client"] = None
                return
        except RuntimeError:
            # No event loop, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Connect to Temporal
        temporal_client = loop.run_until_complete(create_temporal_client())

        # Register client in registry
        config.registry["temporal_client"] = temporal_client
        config.registry.settings["temporal_client"] = temporal_client

        logger.info("Temporal client connected and registered")

    except Exception as e:
        logger.warning("Failed to connect to Temporal server: %s", e)
        # Register None so the app can still start
        config.registry["temporal_client"] = None


def _get_temporal_client(request):
    """Get Temporal client from request registry."""
    return request.registry.get("temporal_client")
