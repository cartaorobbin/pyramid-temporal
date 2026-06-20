# Library Testing

How to test a standalone Pyramid library using a proper application — not in isolation.

## Philosophy

A Pyramid library is consumed by real applications via `config.include()`. Tests should exercise the library the same way consumers use it: by building a real (small) Pyramid application that includes the library and exercises its functionality through actual requests.

Testing with a minimal `Configurator` in isolation — without a WSGI app, without request/response cycles — verifies internal implementation details but misses integration problems. Test like a consumer.

## Test App Structure

Create a small but real Pyramid application inside your test suite:

```
tests/
├── conftest.py          # App factory, testapp fixture, settings
├── test_directives.py   # Tests for custom directives
├── test_tweens.py       # Tests for tweens (via actual requests)
├── test_request.py      # Tests for request methods/properties
└── app/                 # Minimal test application (optional, for complex cases)
    ├── __init__.py      # Composition root for the test app
    └── views.py         # Simple views that exercise library features
```

## Core Fixtures

### App Factory

Build the test app the same way a consumer would — with `config.include()`:

```python
import pytest
from pyramid.config import Configurator
from webtest import TestApp


@pytest.fixture
def app_settings():
    """Settings the test app passes to the library."""
    return {
        "mylib.api_key": "test-key-123",
        "mylib.timeout": "5",
    }


@pytest.fixture
def app(app_settings):
    """A real Pyramid WSGI app that includes the library."""
    with Configurator(settings=app_settings) as config:
        config.include("pyramid_mylib")
        # Add test-specific views that exercise library features
        config.add_route("test_home", "/")
        config.scan("tests.views")
        app = config.make_wsgi_app()
    return app


@pytest.fixture
def testapp(app):
    """WebTest wrapper for making real HTTP requests."""
    return TestApp(app)
```

### Test Views

Simple views inside the test suite that exercise library features — these simulate what a consumer's views would do:

```python
from pyramid.view import view_config


@view_config(route_name="test_home", renderer="json")
def home(request):
    # Exercise a request method added by the library
    client = request.mylib_client
    return {"status": "ok", "client_type": type(client).__name__}
```

## Testing Patterns

### Test the Consumer Experience

Every test should answer: "Does this work when a consumer includes my library and uses it in their app?"

```python
def test_request_method_available(testapp):
    """Consumer can access request.mylib_client after including the library."""
    response = testapp.get("/")
    assert response.json["client_type"] == "MyLibClient"


def test_tween_adds_header(testapp):
    """The timing tween adds X-Request-Time to responses."""
    response = testapp.get("/")
    assert "X-Request-Time" in response.headers
```

### Test Configuration Variants

Consumers will pass different settings. Test the library under different configurations by overriding the `app_settings` fixture with parametrization:

```python
@pytest.fixture(params=[
    {"mylib.timeout": "5"},
    {"mylib.timeout": "60"},
])
def app_settings(request):
    """Parametrize settings to test different configurations."""
    base = {"mylib.api_key": "test-key"}
    base.update(request.param)
    return base


def test_timeout_respected(app_settings, app, testapp):
    """Library respects the timeout setting from the consumer."""
    # Exercise functionality that depends on timeout
    ...
```

### Test Configuration Errors

Verify the library fails clearly when misconfigured:

```python
def test_missing_required_setting_raises():
    """Library raises ConfigurationError when required settings are missing."""
    from pyramid.exceptions import ConfigurationError

    with pytest.raises(ConfigurationError, match="mylib.api_key"):
        with Configurator(settings={}) as config:
            config.include("pyramid_mylib")
            config.commit()
```

### Test Custom Directives

Verify directives are available and functional after include:

```python
def test_directive_registered():
    """After including the library, custom directives are available."""
    with Configurator(settings={"mylib.api_key": "key"}) as config:
        config.include("pyramid_mylib")
        # The directive should now be callable
        assert hasattr(config, "include_widget")


def test_directive_effect(testapp):
    """Calling the custom directive has the expected effect on the app."""
    # Test via a request that exercises the directive's result
    ...
```

### Test Tween Ordering

If your tween depends on position relative to other tweens:

```python
def test_tween_works_with_pyramid_tm():
    """Library tween functions correctly when pyramid_tm is also included."""
    with Configurator(settings={"mylib.api_key": "key"}) as config:
        config.include("pyramid_tm")
        config.include("pyramid_mylib")
        # Exercise request cycle to verify tween ordering
        app = config.make_wsgi_app()
        testapp = TestApp(app)
        response = testapp.get("/")
        assert response.status_code == 200
```

## Testing with External Dependencies

When the library wraps an external service (HTTP API, message queue, etc.):

- **Prefer a real test instance** (Docker container, test account) when practical.
- If a real instance is not available, create a **fake server** within the test suite (using `responses`, `httpretty`, or a local WSGI app) rather than mocking internal library methods.
- The goal is to verify the library's integration behavior, not its unit logic in isolation.

## Continuous Integration

For a standalone library repo, the test matrix should include:
- Multiple Python versions the library supports
- Multiple Pyramid versions (the minimum supported + latest)
- With and without optional dependencies (if the library has optional features)

```ini
# tox.ini or similar
[testenv]
deps =
    pyramid >= 2.0
    webtest
    pytest
commands = pytest
```
