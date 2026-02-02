"""Pyramid environment wrapper for Temporal workers.

This module provides a wrapper around the Pyramid bootstrap environment,
giving Temporal workers access to the full Pyramid application context.
"""

import logging
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from pyramid.registry import Registry

logger = logging.getLogger(__name__)


class PyramidEnvironment:
    """Wrapper for Pyramid bootstrap environment.

    This class wraps the output of pyramid.paster.bootstrap, providing
    structured access to the Pyramid application components.

    Attributes:
        registry: The Pyramid registry
        app: The WSGI application
        request: The base request object
        root: The root object (for traversal-based applications)

    Example:
        from pyramid.paster import bootstrap
        from pyramid_temporal import PyramidEnvironment

        # Create from bootstrap output
        env_dict = bootstrap('development.ini')
        env = PyramidEnvironment.from_bootstrap(env_dict)

        # Access components
        settings = env.settings
        registry = env.registry

        # Clean up when done
        env.close()
    """

    def __init__(
        self,
        registry: "Registry",
        app: Optional[Any] = None,
        request: Optional[Any] = None,
        root: Optional[Any] = None,
        closer: Optional[Callable[[], None]] = None,
    ) -> None:
        """Initialize the Pyramid environment.

        Args:
            registry: Pyramid registry instance (required)
            app: WSGI application instance
            request: Base request object from bootstrap
            root: Root object for traversal-based applications
            closer: Cleanup callable from bootstrap
        """
        self._registry = registry
        self._app = app
        self._request = request
        self._root = root
        self._closer = closer

        logger.debug("Created PyramidEnvironment with registry: %s", registry)

    @classmethod
    def from_bootstrap(cls, env: dict) -> "PyramidEnvironment":
        """Create a PyramidEnvironment from bootstrap output.

        This is the preferred way to create a PyramidEnvironment when
        using pyramid.paster.bootstrap.

        Args:
            env: Dictionary returned by pyramid.paster.bootstrap()

        Returns:
            PyramidEnvironment instance

        Example:
            from pyramid.paster import bootstrap
            from pyramid_temporal import PyramidEnvironment

            env = PyramidEnvironment.from_bootstrap(bootstrap('development.ini'))
        """
        return cls(
            registry=env["registry"],
            app=env.get("app"),
            request=env.get("request"),
            root=env.get("root"),
            closer=env.get("closer"),
        )

    @property
    def registry(self) -> "Registry":
        """Get the Pyramid registry."""
        return self._registry

    @property
    def app(self) -> Optional[Any]:
        """Get the WSGI application."""
        return self._app

    @property
    def request(self) -> Optional[Any]:
        """Get the base request object from bootstrap."""
        return self._request

    @property
    def root(self) -> Optional[Any]:
        """Get the root object for traversal-based applications."""
        return self._root

    @property
    def settings(self) -> dict:
        """Get application settings (shortcut to registry.settings)."""
        return self._registry.settings

    def close(self) -> None:
        """Clean up resources.

        This calls the closer function from bootstrap to properly
        clean up the Pyramid application.
        """
        if self._closer is not None:
            logger.debug("Closing PyramidEnvironment")
            self._closer()

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<PyramidEnvironment registry={self._registry}>"
