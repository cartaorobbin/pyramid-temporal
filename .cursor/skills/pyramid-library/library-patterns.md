# Library Patterns

How to design a standalone Pyramid extension that consumers include via `config.include('your_library')`.

## Package Structure

A Pyramid library is a standard Python package with one critical contract: it exposes `def includeme(config)` at its top-level `__init__.py` (or in a module the consumer explicitly includes).

```
pyramid_mylib/
├── __init__.py          # includeme lives here
├── directives.py        # custom config directives (if any)
├── tweens.py            # tween factories (if any)
├── settings.py          # settings parsing and defaults
├── request_methods.py   # request property/method additions (if any)
└── ...
```

The package name convention is `pyramid_<name>` (underscore, not hyphen). This follows the ecosystem convention (`pyramid_tm`, `pyramid_services`, `pyramid_mailer`).

## The `includeme` Contract

The library's `includeme` is the sole entry point. It must:

1. **Be self-contained** — a single `config.include('pyramid_mylib')` in the consumer's composition root should activate all library functionality.
2. **Declare dependencies** — if the library depends on another Pyramid extension, include it: `config.include('pyramid_tm')`. This makes include order less fragile for the consumer.
3. **Read settings defensively** — the consumer may not have set all your settings. Always provide defaults.
4. **Never assume app internals** — no imports from the host app, no `BaseService`, no app-specific models, no assumptions about which other domain packages exist.

```python
def includeme(config):
    settings = config.registry.settings

    # Read settings with defaults
    prefix = settings.get("mylib.prefix", "/api")
    timeout = int(settings.get("mylib.timeout", "30"))

    # Register what the library provides
    config.add_directive("do_mylib_thing", directives.do_mylib_thing_directive)
    config.add_request_method(request_methods.get_mylib_client, "mylib", reify=True)
    config.add_tween("pyramid_mylib.tweens.timing_tween_factory")
```

## Settings Conventions

- **Prefix all settings** with the library name: `mylib.timeout`, `mylib.api_key`, `mylib.enabled`.
- **Provide sensible defaults** for every setting. The library should work with zero configuration for common use cases.
- **Parse settings in includeme** (or a helper called from it), not at import time.
- **Validate early** — if a required setting is missing, raise a `ConfigurationError` from `includeme` with a clear message. Don't wait until runtime to fail.

```python
from pyramid.exceptions import ConfigurationError

def includeme(config):
    settings = config.registry.settings
    api_key = settings.get("mylib.api_key")
    if not api_key:
        raise ConfigurationError(
            "pyramid_mylib requires 'mylib.api_key' in settings. "
            "Add it to your .ini file or pass it to the Configurator."
        )
```

## Custom Directives

Libraries register directives in `includeme` to extend the `Configurator` for consumers. For the full directive API, `config.action()`, and conflict detection, see the **pyramid-core** skill's `configuration.md`.

Key library-specific concerns:

- **Design for consumers** — the directive is part of the library's public API. Name it clearly and document its parameters.
- **Use `config.action()` with discriminators** — libraries may be included by multiple consumers. Conflict detection prevents silent overwrites (see pyramid-core `configuration.md` for details).
- **Don't assume context** — the directive will be called from the consumer's `includeme`, not yours.

```python
def include_widget_directive(config, widget_path):
    """Directive that consumers call as config.include_widget('path.to.widget')."""
    config.include(widget_path)

def includeme(config):
    config.add_directive("include_widget", include_widget_directive)
```

After including the library, consumers can call `config.include_widget(...)` in their own `includeme` functions.

## Tweens

Libraries register tweens with explicit positioning so they integrate correctly with the consumer's tween chain. For the full tween factory protocol, ordering mechanics, and common patterns, see the **pyramid-core** skill's `tweens.md`.

Key library-specific concerns:

- **Always declare position** with `over=` or `under=` — consumers shouldn't need to worry about tween order. A library that omits positioning forces the consumer to figure it out.
- **Document the position assumption** — explain why the tween needs to be above or below specific tweens.
- **Use the dotted name** — `config.add_tween("pyramid_mylib.tweens.factory")`, not the factory object.

```python
def includeme(config):
    config.add_tween(
        "pyramid_mylib.tweens.timing_tween_factory",
        under="pyramid_tm.tm_tween_factory",
    )
```

## Request Methods and Properties

Libraries add reified properties or callable methods to the request object so consumers access library functionality via `request.mylib_client`. For the full `add_request_method` API (reify vs property vs callable, registration patterns), see the **pyramid-core** skill's `request-and-response.md`.

Key library-specific concerns:

- **Namespace the attribute** — use the library name to avoid collisions (e.g., `mylib_client`, not `client`).
- **Prefer `reify=True`** — most library-provided request objects should be created lazily and cached per request.
- **Don't require setup** — the request method should work after a single `config.include()` with no extra steps.

```python
def get_mylib_client(request):
    settings = request.registry.settings
    return MyLibClient(api_key=settings["mylib.api_key"])

def includeme(config):
    config.add_request_method(get_mylib_client, "mylib_client", reify=True)
```

## Registry Attributes for Singletons

For app-wide objects that outlive individual requests (connection pools, caches, HTTP clients), store them on the registry. For the full pattern including combining registry attributes with request methods, see the **pyramid-core** skill's `request-and-response.md`.

```python
def includeme(config):
    settings = config.registry.settings
    pool = create_connection_pool(settings["mylib.pool_size"])
    config.registry.mylib_pool = pool
```

Access at runtime via `request.registry.mylib_pool`. This is appropriate for thread-safe, long-lived objects.

## What a Library Must NOT Do

- **Import from the host app** — no `from main.services import BaseService`, no app models, no app-specific interfaces.
- **Assume database access** — the consumer may not use SQLAlchemy, or may use a different session setup. If the library needs a session, accept it as a setting or require the consumer to provide it via a hook.
- **Register routes directly** (unless that's the library's purpose) — prefer providing directives that let the consumer control URL space.
- **Call `config.scan()` on consumer packages** — only scan the library's own modules.
- **Depend on include order from the consumer** — if the library needs another extension, include it yourself in your `includeme`.

## Events

Libraries can subscribe to Pyramid events to react to request lifecycle stages without modifying the response. For the full event system (built-in events, custom events, subscriber predicates), see the **pyramid-core** skill's `events.md`.

Key library-specific concerns:

- **Prefer events over tweens for observation** — if the library only needs to observe (not modify) requests/responses, use event subscribers instead of tweens.
- **Scan the library's own subscriber module** — don't rely on the consumer scanning your code.
- **Fire custom events** for extensibility — let consumers subscribe to library-specific events rather than requiring callback hooks.

```python
from pyramid.events import NewRequest, subscriber

@subscriber(NewRequest)
def on_new_request(event):
    event.request.mylib_start_time = time.time()

def includeme(config):
    config.scan("pyramid_mylib.subscribers")
```
