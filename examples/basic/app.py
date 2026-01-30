"""Simple Pyramid application for the basic example.

This module provides a minimal Pyramid application factory that can be used
with the ptemporal-worker command.
"""

from pyramid.config import Configurator


def main(global_config, **settings):
    """Create a minimal Pyramid application.

    This function serves as the application factory for the basic example.
    It creates a Pyramid application with pyramid-temporal included.

    Args:
        global_config: Global configuration from INI file
        **settings: Application settings from INI file

    Returns:
        WSGI application
    """
    # Create Pyramid configurator
    config = Configurator(settings=settings)

    # Include pyramid-temporal
    config.include("pyramid_temporal")

    # Create and return WSGI application
    return config.make_wsgi_app()
