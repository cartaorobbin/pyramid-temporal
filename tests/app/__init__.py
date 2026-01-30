"""Test application package."""

import logging

from pyramid.config import Configurator
from pyramid.request import Request
from sqlalchemy.orm import sessionmaker

from tests.app.models import get_tm_session

logger = logging.getLogger(__name__)


def get_db_session(request: Request):
    """Get database session from request registry.

    Following legal-entity pattern: check for test dbsession in environ first,
    then fall back to creating new session with transaction manager.
    """
    # Check for test dbsession in environ (for test isolation)
    dbsession = request.environ.get("app.dbsession")
    if dbsession is not None:
        return dbsession

    # Normal operation: create session with transaction manager
    session_factory = request.registry.get("dbsession_factory")
    if session_factory:
        return get_tm_session(session_factory, request.tm, request=request)

    # Fallback for basic tests
    return request.registry.dbmaker()


def create_app(db_session_maker: sessionmaker, settings: dict = None):
    """Create and configure the test Pyramid application.

    Args:
        db_session_maker: SQLAlchemy session maker
        settings: Optional dictionary of Pyramid settings

    Returns:
        Pyramid WSGI application
    """
    # Use provided settings or empty dict
    app_settings = settings or {}

    # Create configurator with settings
    config = Configurator(settings=app_settings)

    # Include pyramid_tm for web request transaction management
    config.include("pyramid_tm")

    # Include pyramid_temporal for activity transaction management
    # This will handle Temporal client setup based on settings
    config.include("pyramid_temporal")

    # Register database session maker
    config.registry.dbmaker = db_session_maker

    # Add request method to get database session
    config.add_request_method(get_db_session, "dbsession", reify=True)

    # Add routes
    config.add_route("create_user", "/users")

    # Scan for view configurations
    config.scan("tests.app.views")

    logger.info("Test Pyramid application configured")

    # Create and return WSGI app
    return config.make_wsgi_app()
