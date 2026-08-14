"""Pytest fixtures for pyramid-temporal integration tests."""

import asyncio
import logging
import threading
import time
import uuid
from datetime import timedelta

import pytest
import transaction
from pyramid.config import Configurator
from pyramid.request import Request, apply_request_extensions
from sqlalchemy import create_engine
from temporalio.client import Client
from testing.postgresql import PostgresqlFactory
from webtest import TestApp

from pyramid_temporal import PyramidEnvironment, Worker
from tests.app import create_app
from tests.app.concurrent import (
    PROBE_TASK_QUEUE,
    ConcurrentAsyncAbortWorkflow,
    ConcurrentAsyncIsolationWorkflow,
    ConcurrentAsyncProbeWorkflow,
    ConcurrentSyncAbortWorkflow,
    ConcurrentSyncIsolationWorkflow,
    ConcurrentSyncProbeWorkflow,
    async_abort_activity,
    async_commit_activity,
    async_isolation_activity,
    async_probe_activity,
    reset_rendezvous,
    sync_abort_activity,
    sync_commit_activity,
    sync_isolation_activity,
    sync_probe_activity,
)
from tests.app.models import Base, get_session_maker, get_tm_session
from tests.app.workflows import UserEnrichmentWorkflow, enrich_user_activity

logger = logging.getLogger(__name__)

# Temporal server address. The devcontainer runs Temporal as the "temporal"
# compose service, reachable from the dev container by that service name.
TEMPORAL_HOST = "temporal:7233"


def handler(postgresql):
    """Handler for PostgreSQL initialization."""
    pass


# Create PostgreSQL factory with caching for efficient tests
PostgresqlTest = PostgresqlFactory(cache_initialized_db=True, on_initialized=handler)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def dbengine():
    """Create PostgreSQL database engine for testing.

    This fixture is module-scoped for efficiency, following legal-entity pattern.
    """
    postgresql = PostgresqlTest()

    # Create engine with PostgreSQL URL
    engine = create_engine(postgresql.url())

    # Create all tables
    Base.metadata.create_all(bind=engine)

    yield engine

    # Cleanup
    Base.metadata.drop_all(bind=engine)
    postgresql.stop()


@pytest.fixture(scope="module")
def db_session_factory(dbengine):
    """Create SQLAlchemy session factory."""
    return get_session_maker(dbengine)


@pytest.fixture
def tm():
    """Create transaction manager for test isolation.

    For pyramid-temporal integration test, we need to allow commits
    so the activity changes are visible to the test verification.
    """
    tm = transaction.TransactionManager(explicit=True)
    tm.begin()
    tm.doom()

    yield tm

    tm.abort()


@pytest.fixture
def dbsession(db_session_factory, tm):
    """Create database session with transaction management.

    This session is tied to the test transaction manager and will be
    rolled back automatically after each test.
    """
    return get_tm_session(db_session_factory, tm)


@pytest.fixture
def temporal_host():
    """Temporal server address used by the tests."""
    return TEMPORAL_HOST


@pytest.fixture
def configured_request():
    """Return a factory that builds a request bound to a configured pyramid_temporal registry.

    The factory accepts an optional settings dict and returns a real Pyramid request with
    pyramid_temporal request methods applied, so client helpers can be exercised without a
    running WSGI app.
    """

    def _make(extra_settings: dict = None) -> Request:
        config = Configurator(settings={"pyramid_temporal.auto_connect": "false", **(extra_settings or {})})
        config.include("pyramid_temporal")
        config.commit()
        request = Request.blank("/")
        request.registry = config.registry
        apply_request_extensions(request)
        return request

    return _make


@pytest.fixture
def app_settings():
    """Create base application settings for testing."""
    return {
        "pyramid_temporal.temporal_host": TEMPORAL_HOST,
        "pyramid_temporal.auto_connect": "true",  # Always enable Temporal for our tests
        "pyramid_temporal.task_queue": "pyramid-temporal-test",
        "pyramid_temporal.log_level": "DEBUG",
    }


@pytest.fixture
def temporal_client():
    """Create Temporal client for testing.

    Requires a running Temporal server reachable at TEMPORAL_HOST. The
    devcontainer provides it as the "temporal" compose service; if it is
    unavailable the dependent tests are skipped.
    """
    try:
        # Try to connect to local Temporal server
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def create_client():
            return await Client.connect(TEMPORAL_HOST)

        client = loop.run_until_complete(create_client())
        yield client
        loop.close()

    except Exception as e:
        pytest.skip(f"Temporal server not available: {e}")


@pytest.fixture
def temporal_worker(temporal_client, pyramid_app, dbsession, tm):
    """Create a pyramid-temporal Worker bound to the test session and transaction.

    pyramid-temporal builds a real Pyramid request for each activity. We expose
    the test's session and transaction manager through that request's environ so
    the activity shares the exact session the test verifies against, and the
    test's doomed transaction rolls everything back afterwards.

    Note: the activity runs on the worker thread and shares the test's session,
    so the test must rely on ``poll_query`` for synchronization (it waits for the
    activity to finish) rather than reading the session concurrently.
    """
    env_request = Request.blank("/")
    env_request.environ["app.dbsession"] = dbsession
    env_request.environ["tm.manager"] = tm
    env_request.environ["tm.active"] = True

    env = PyramidEnvironment(registry=pyramid_app.registry, request=env_request)

    worker = Worker(
        temporal_client,
        env,
        task_queue="pyramid-temporal-test",
        workflows=[UserEnrichmentWorkflow],
        activities=[enrich_user_activity],
    )

    # Start worker in background thread. Temporal queues the workflow until the
    # worker polls, so no startup sleep is needed; poll_query waits for the result.
    def run_worker():
        asyncio.set_event_loop(asyncio.new_event_loop())
        asyncio.get_event_loop().run_until_complete(worker.run())

    worker_thread = threading.Thread(target=run_worker, daemon=True)
    worker_thread.start()

    yield worker

    # Worker will be automatically cleaned up when thread exits


@pytest.fixture
def pyramid_env():
    """Return a PyramidEnvironment backed by a minimal registry, without a database.

    Enough to build activity requests, so the binding tests can exercise a full
    activity execution without a Temporal server or a database.
    """
    config = Configurator(settings={"pyramid_temporal.auto_connect": "false"})
    config.include("pyramid_temporal")
    config.commit()
    return PyramidEnvironment(registry=config.registry)


@pytest.fixture
def run_workflow(temporal_client, pyramid_env):
    """Return a function that runs one workflow to completion on a worker of its own.

    The worker lives only for the call, and the environment carries no base
    request, so each activity execution builds its own. The execution timeout
    bounds the wait: a workflow task that keeps failing is retried forever by
    Temporal, and without the timeout the caller would block instead of failing.
    """

    def _run(workflow_cls: type, arg, *, activities: list, task_queue: str):
        worker = Worker(
            temporal_client,
            pyramid_env,
            task_queue=task_queue,
            activities=activities,
            workflows=[workflow_cls],
        )

        async def serve_and_execute():
            async with worker:
                return await temporal_client.execute_workflow(
                    workflow_cls.run,
                    arg,
                    id=f"{task_queue}-{uuid.uuid4().hex[:8]}",
                    task_queue=task_queue,
                    execution_timeout=timedelta(seconds=20),
                )

        return asyncio.get_event_loop().run_until_complete(serve_and_execute())

    return _run


@pytest.fixture
def probe_labels():
    """Two unique labels, one per concurrent probe execution."""
    run = uuid.uuid4().hex[:8]
    return [f"probe-{run}-a", f"probe-{run}-b"]


@pytest.fixture
def reset_probes():
    """Clear the probe rendezvous state around each batch of executions."""
    reset_rendezvous()
    yield
    reset_rendezvous()


@pytest.fixture
def concurrent_worker(temporal_client, pyramid_app, reset_probes):
    """Run a worker with two activity slots and no shared request state.

    The environment carries no base request, so nothing injects a shared
    dbsession or transaction manager: each execution builds its own session and
    its own transaction manager through pyramid_tm's explicit_manager hook, and
    commits for real. That is what lets the tests observe per-execution
    transactions.

    The worker is served through ``async with`` and shut down on teardown, so a
    finished test never leaves a poller competing for the next test's tasks.
    """
    env = PyramidEnvironment(registry=pyramid_app.registry)

    worker = Worker(
        temporal_client,
        env,
        task_queue=PROBE_TASK_QUEUE,
        workflows=[
            ConcurrentAsyncAbortWorkflow,
            ConcurrentAsyncIsolationWorkflow,
            ConcurrentAsyncProbeWorkflow,
            ConcurrentSyncAbortWorkflow,
            ConcurrentSyncIsolationWorkflow,
            ConcurrentSyncProbeWorkflow,
        ],
        activities=[
            async_abort_activity,
            async_commit_activity,
            async_isolation_activity,
            async_probe_activity,
            sync_abort_activity,
            sync_commit_activity,
            sync_isolation_activity,
            sync_probe_activity,
        ],
        max_concurrent_activities=2,
    )

    stop = threading.Event()

    async def serve():
        async with worker:
            while not stop.is_set():
                await asyncio.sleep(0.05)

    def run_worker():
        asyncio.set_event_loop(asyncio.new_event_loop())
        asyncio.get_event_loop().run_until_complete(serve())

    worker_thread = threading.Thread(target=run_worker, daemon=True)
    worker_thread.start()

    yield worker

    stop.set()
    worker_thread.join(timeout=15)


@pytest.fixture
def pyramid_app(dbengine, db_session_factory, app_settings):
    """Create test Pyramid application with Temporal integration."""

    # Override sqlalchemy.url to use test database
    settings = app_settings.copy()
    settings["sqlalchemy.url"] = str(dbengine.url)
    settings["tm.manager_hook"] = "pyramid_tm.explicit_manager"

    app = create_app(db_session_factory, settings)
    app.registry["dbsession_factory"] = db_session_factory
    app.registry["dbengine"] = dbengine

    return app


@pytest.fixture
def webtest_app(pyramid_app, tm, dbsession):
    """Create WebTest TestApp with transaction isolation."""
    testapp = TestApp(
        pyramid_app,
        extra_environ={
            "HTTP_HOST": "example.com",
            "REMOTE_ADDR": "192.168.0.1",
            "tm.active": True,
            "tm.manager": tm,
            "app.dbsession": dbsession,
        },
    )
    return testapp


@pytest.fixture
def poll_query(dbsession):
    """Fixture that returns a function to poll for query results.

    Returns a function that polls the database until a query returns results.
    """

    def _poll(query, timeout: float = 10.0, interval: float = 0.5, description: str = "query") -> bool:
        """Poll database until query returns results or timeout.

        Args:
            query: SQLAlchemy query to execute
            timeout: Maximum time to wait in seconds
            interval: Time between checks in seconds
            description: Description of what we're polling for (for logging)

        Returns:
            bool: True if query returned results, False if timeout
        """
        logger.info("Starting to poll for %s", description)
        start_time = time.time()

        while time.time() - start_time < timeout:
            # Refresh session and execute query
            dbsession.expire_all()
            result = query.first()

            if result:
                logger.info("Poll successful: %s found", description)
                return True
            else:
                logger.debug("Polling: %s not found yet", description)

            time.sleep(interval)

        logger.warning("Timeout waiting for %s", description)
        return False

    return _poll
