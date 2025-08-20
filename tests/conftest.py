"""Pytest fixtures for pyramid-temporal integration tests."""

import asyncio
import logging
import threading
import time
from typing import Generator

import pytest
import transaction
from pyramid.config import Configurator
from pyramid.request import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from temporalio.client import Client
from temporalio.worker import Worker
from testing.postgresql import PostgresqlFactory
from webtest import TestApp

from pyramid_temporal import PyramidTemporalInterceptor
from tests.app import create_app
from tests.app.models import Base, User, create_tables, get_session_maker, get_tm_session
from tests.app.workflows import UserEnrichmentWorkflow, enrich_user_activity

logger = logging.getLogger(__name__)


def handler(postgresql):
    """Handler for PostgreSQL initialization."""
    pass


# Create PostgreSQL factory with caching for efficient tests
PostgresqlTest = PostgresqlFactory(
    cache_initialized_db=True, 
    on_initialized=handler
)


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
def app_settings():
    """Create base application settings for testing."""
    return {
        'pyramid_temporal.temporal_host': 'localhost:7233',
        'pyramid_temporal.auto_connect': 'true',  # Always enable Temporal for our tests
        'pyramid_temporal.log_level': 'DEBUG',
    }


@pytest.fixture
def temporal_client():
    """Create Temporal client for testing.
    
    Note: This requires a running Temporal server.
    Start with: docker-compose -f .dev-local/docker-compose.yml up -d
    """
    try:
        # Try to connect to local Temporal server
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def create_client():
            return await Client.connect("localhost:7233")
        
        client = loop.run_until_complete(create_client())
        yield client
        loop.close()
        
    except Exception as e:
        pytest.skip(f"Temporal server not available: {e}")


@pytest.fixture
def temporal_worker(temporal_client, dbsession, tm):
    """Create Temporal worker with pyramid_temporal interceptor."""
    
    # Create a session factory that returns the test session
    # This ensures the temporal worker uses the same session as the test
    def test_session_factory():
        return dbsession
    
    # Create worker with pyramid_temporal transaction management
    worker = Worker(
        temporal_client,
        task_queue="pyramid-temporal-test",
        workflows=[UserEnrichmentWorkflow],
        activities=[enrich_user_activity],
        interceptors=[PyramidTemporalInterceptor(
            db_session_factory=test_session_factory,
            transaction_manager=tm  # Use the test's transaction manager
        )],
    )
    
    # Start worker in background thread
    def run_worker():
        asyncio.set_event_loop(asyncio.new_event_loop())
        asyncio.get_event_loop().run_until_complete(worker.run())
    
    worker_thread = threading.Thread(target=run_worker, daemon=True)
    worker_thread.start()
    
    # Give worker a moment to start
    time.sleep(1)
    
    yield worker
    
    # Worker will be automatically cleaned up when thread exits


@pytest.fixture
def pyramid_app(dbengine, db_session_factory, app_settings):
    """Create test Pyramid application with Temporal integration."""
    
    # Override sqlalchemy.url to use test database
    settings = app_settings.copy()
    settings['sqlalchemy.url'] = str(dbengine.url)
    settings["tm.manager_hook"] = "pyramid_tm.explicit_manager"
    
    app = create_app(db_session_factory, settings)
    app.registry['dbsession_factory'] = db_session_factory
    app.registry['dbengine'] = dbengine
    
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
