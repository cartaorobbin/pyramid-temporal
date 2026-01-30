"""Command line interface for pyramid-temporal.

This module provides the ptemporal-worker command for starting Temporal workers
with Pyramid application configuration.
"""

import asyncio
import importlib
import logging
import sys
from typing import Callable

import click
from pyramid.paster import bootstrap, setup_logging
from temporalio.worker import Worker

logger = logging.getLogger(__name__)


def _import_worker_factory(worker_path: str) -> Callable:
    """Import and return a worker factory function from a Python path.

    Args:
        worker_path: Python import path like 'myapp.workers.create_worker'

    Returns:
        Callable: The worker factory function

    Raises:
        ImportError: If the module or function cannot be imported
        AttributeError: If the function doesn't exist in the module
    """
    try:
        module_path, function_name = worker_path.rsplit(".", 1)
    except ValueError:
        raise ValueError(f"Invalid worker path: '{worker_path}'. " "Expected format: 'module.path.function_name'")

    try:
        module = importlib.import_module(module_path)
        worker_factory = getattr(module, function_name)
    except ImportError as e:
        raise ImportError(f"Cannot import module '{module_path}': {e}")
    except AttributeError:
        raise AttributeError(f"Function '{function_name}' not found in module '{module_path}'")

    if not callable(worker_factory):
        raise TypeError(
            f"'{worker_path}' is not callable. " "Worker factory must be a function that returns a Worker instance."
        )

    return worker_factory


def _bootstrap_pyramid(ini_file: str) -> dict:
    """Bootstrap Pyramid application from INI file.

    Args:
        ini_file: Path to the Pyramid INI configuration file (already validated by Click)

    Returns:
        dict: Bootstrap environment with 'app', 'registry', 'request', 'root', 'closer'

    Raises:
        Exception: If configuration fails
    """
    logger.info("Setting up logging from INI file: %s", ini_file)
    setup_logging(ini_file)

    logger.info("Bootstrapping Pyramid application from INI file: %s", ini_file)
    env = bootstrap(ini_file)

    logger.info("Pyramid bootstrap complete")
    logger.info("Registry: %s", env["registry"])
    logger.info("Application: %s", env["app"])

    return env


async def _run_worker(worker: Worker) -> None:
    """Run the Temporal worker forever.

    Args:
        worker: Temporal Worker instance to run
    """
    logger.info("Starting Temporal worker...")
    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down worker...")
    except Exception as e:
        logger.error("Worker failed with error: %s", e)
        raise
    finally:
        logger.info("Worker shutdown complete")


@click.command()
@click.argument("ini_file", type=click.Path(exists=True, readable=True))
@click.argument("worker_factory_path")
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    help="Override log level (default: INFO)",
)
def ptemporal_worker(ini_file: str, worker_factory_path: str, log_level: str) -> None:
    """Start a Temporal worker with Pyramid configuration.

    This command bootstraps a Pyramid application from an INI file and starts
    a Temporal worker using a user-provided worker factory function.

    Args:
        ini_file: Path to Pyramid INI configuration file
        worker_factory_path: Python import path to worker factory function
                            (e.g., 'myapp.workers.create_worker')

    The worker factory function should accept a Pyramid registry as its
    only argument and return a configured temporalio.worker.Worker instance.

    Example:
        ptemporal-worker development.ini myapp.workers.create_worker

    Example worker factory function:

        def create_worker(registry):
            from temporalio.worker import Worker
            from pyramid_temporal import PyramidTemporalInterceptor

            # Get Temporal client from registry
            client = registry.get('temporal_client')
            if not client:
                raise RuntimeError("Temporal client not found in registry")

            return Worker(
                client,
                task_queue="my-queue",
                workflows=[MyWorkflow],
                activities=[my_activity],
                interceptors=[PyramidTemporalInterceptor()]
            )
    """
    # Set up basic logging if not already configured
    logging.basicConfig(
        level=getattr(logging, log_level), format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger.info("Starting ptemporal-worker")
    logger.info("INI file: %s", ini_file)
    logger.info("Worker factory: %s", worker_factory_path)

    try:
        # 1. Bootstrap Pyramid application
        logger.info("Step 1: Bootstrapping Pyramid application")
        env = _bootstrap_pyramid(ini_file)
        registry = env["registry"]

        # 2. Import worker factory function
        logger.info("Step 2: Importing worker factory function")
        worker_factory = _import_worker_factory(worker_factory_path)

        # 3. Create worker using factory
        logger.info("Step 3: Creating Temporal worker")
        worker = worker_factory(registry)

        if not isinstance(worker, Worker):
            raise TypeError(f"Worker factory must return a temporalio.worker.Worker instance, " f"got {type(worker)}")

        # 4. Run worker
        logger.info("Step 4: Starting worker (this will run forever)")

        try:
            asyncio.run(_run_worker(worker))
        finally:
            # Clean up pyramid bootstrap environment
            logger.info("Cleaning up Pyramid environment")
            env["closer"]()

    except Exception as e:
        logger.error("Failed to start worker: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    ptemporal_worker()
