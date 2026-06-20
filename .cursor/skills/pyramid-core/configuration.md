# Configuration Extensions

Pyramid's extension points for the `Configurator` — scanning, custom directives, conflict detection, view/route predicates, view derivers, and static asset serving.

---

## 1. Scanning (`config.scan()`)

`config.scan()` discovers and registers decorator-based configuration — `@view_config`, `@subscriber`, `@forbidden_view_config`, and any other Pyramid venusian-based decorators — by inspecting Python modules at configuration time.

### How It Works

Decorators like `@view_config` don't register anything at import time. They attach metadata to the decorated function. `config.scan()` walks through the specified package, finds that metadata, and calls the actual registration (e.g., `config.add_view()`).

```python
from pyramid.view import view_config

@view_config(route_name="home", renderer="json")
def home_view(request):
    return {"status": "ok"}
```

Without `config.scan()`, this view is never registered and Pyramid won't route to it.

### Scanning a Specific Package

```python
def includeme(config):
    config.scan("billing.views")
```

Scans only the `billing.views` package and its submodules. This is the preferred approach — explicit about what gets scanned.

### Scanning the Current Package

Use relative paths to scan the current package:

```python
def includeme(config):
    config.scan(".")
```

Or with no arguments (scans the caller's package):

```python
def includeme(config):
    config.scan()
```

### The `ignore=` Parameter

When a domain package's `includeme` explicitly includes subpackages (via `config.include()`), those subpackages have already been processed. Scanning them again would cause double registration. Use `ignore=` to skip them:

```python
def includeme(config):
    config.include(".models")
    config.include(".services")
    config.include(".routes")
    config.scan(ignore=[".models", ".services", ".routes"])
```

Only ignore subpackages that have their own `includeme` and were explicitly included. Subpackages without `includeme` (like `schemas/`) should be scanned normally.

### Placement Rules

- **Call `config.scan()` at the end of `includeme`**, after all `config.include()` calls. This ensures that routes, services, and directives are registered before the views that depend on them are discovered.
- **Never call `config.scan()` at module level** — only inside `includeme`. Scanning is a configuration-time operation.
- **Libraries should only scan their own modules** — never `config.scan()` the consumer's packages.

### `config.scan()` vs `config.include()`

| | `config.scan()` | `config.include()` |
|---|---|---|
| **Discovers** | Decorator-based registrations (`@view_config`, `@subscriber`) | `def includeme(config)` entry points |
| **Activates** | Decorators attached to functions/classes | Explicit `config.*` calls inside `includeme` |
| **Use for** | Views, event subscribers, any venusian decorator | Module wiring, services, routes, subpackage includes |

Both are needed — `config.include()` for explicit configuration, `config.scan()` for decorator-based configuration.

### Category Filtering

Scan specific categories of decorators:

```python
config.scan("mypackage", categories=["pyramid"])
```

This only discovers Pyramid-specific decorators, ignoring decorators from other frameworks. Rarely needed in practice — the default scans all categories.

---

## 2. Custom Directives

`config.add_directive()` extends the `Configurator` with new methods. After registration, any `includeme` (or the composition root) can call the directive as `config.your_directive(...)`.

### Basic Directive

A directive is a function whose first argument is the `Configurator`:

```python
def add_api_route(config, name, pattern, **kwargs):
    """Directive that adds a route with the /api/v1 prefix."""
    full_pattern = f"/api/v1{pattern}"
    config.add_route(name, full_pattern, **kwargs)

def includeme(config):
    config.add_directive("add_api_route", add_api_route)
```

After this `includeme` runs, any module can call:

```python
def includeme(config):
    config.add_api_route("users.list", "/users")
    config.add_api_route("users.detail", "/users/{uuid}")
```

### Directive Signature

```python
def my_directive(config, arg1, arg2, **kwargs):
    ...
```

The first argument is always the `Configurator` instance. The rest are whatever arguments the directive needs. Pyramid binds the directive as a method on the config object, so callers write `config.my_directive(arg1, arg2)`.

### When to Create Directives

- **Shared patterns** — when multiple modules repeat the same configuration steps (e.g., adding routes with a prefix, registering services with boilerplate)
- **Library APIs** — when a library needs to expose configuration to its consumers (see **pyramid-library** skill)
- **Convention enforcement** — when a pattern should be consistent across the codebase

---

## 3. `config.action()` and Conflict Detection

For simple app-internal directives, calling `config.add_route()` or other built-in methods directly inside the directive is sufficient. But when writing library-quality directives that might be called multiple times with conflicting arguments, use `config.action()` to participate in Pyramid's conflict detection.

### How It Works

Pyramid's configuration is two-phase:

1. **Registration phase** — `includeme` functions run, calling directives that queue actions via `config.action()`.
2. **Commit phase** — `config.commit()` (called by `config.make_wsgi_app()`) executes all queued actions. If two actions have the same discriminator, Pyramid raises a `ConfigurationConflictError`.

### Using `config.action()`

```python
def add_cache_backend(config, name, factory):
    """Register a named cache backend. Conflicts if the same name is registered twice."""

    def register():
        config.registry.cache_backends[name] = factory

    # The discriminator identifies this action uniquely
    discriminator = ("cache_backend", name)
    config.action(discriminator, register)

def includeme(config):
    config.registry.cache_backends = {}
    config.add_directive("add_cache_backend", add_cache_backend)
```

If two modules both call `config.add_cache_backend("default", ...)`, Pyramid raises a conflict error at startup rather than silently overwriting.

### Discriminator Design

The discriminator is a hashable value (typically a tuple) that uniquely identifies the action:

- `("route", "users.list")` — a route named `users.list`
- `("cache_backend", "default")` — a cache backend named `default`
- `("tween", "mylib.timing")` — a tween with a specific dotted name

Actions with different discriminators never conflict. Actions with the same discriminator conflict unless they come from the same `config.include()` call.

### When `config.action()` Is Necessary

| Scenario | Need `config.action()`? |
|----------|------------------------|
| App-internal directive, called once | No — direct calls are fine |
| Library directive, consumers might call multiple times | Yes — detect conflicts |
| Directive wrapping built-in methods (which already use actions) | Optional — built-ins handle their own conflicts |

---

## 4. View Predicates

`config.add_view_predicate()` registers a custom predicate that Pyramid uses to select which view to invoke. Built-in predicates include `request_method`, `route_name`, `context`, and `permission`. Custom predicates add application-specific criteria.

### Predicate Factory

A view predicate is a class with this protocol:

```python
class HeaderPredicate:
    def __init__(self, val, config):
        """val is the value passed by the user: @view_config(require_header="X-Api-Key")."""
        self.header_name = val

    def text(self):
        """Human-readable description for debugging (proutes, pviews)."""
        return f"require_header = {self.header_name}"

    def phash(self):
        """Hash for predicate identity — views with different phash are distinct."""
        return self.text()

    def __call__(self, context, request):
        """Return True if this predicate matches the current request."""
        return self.header_name in request.headers
```

### Registration

```python
def includeme(config):
    config.add_view_predicate("require_header", HeaderPredicate)
```

### Usage in Views

```python
@view_config(route_name="api.data", renderer="json", require_header="X-Api-Key")
def api_data_view(request):
    return {"data": "sensitive"}
```

Pyramid will only invoke this view if the `X-Api-Key` header is present. If the predicate fails, Pyramid continues searching for a matching view (or returns 404).

### Predicate Weighting

Predicates have a natural ordering. Pyramid selects the most specific matching view. Custom predicates are evaluated after built-in ones unless you override the weighting.

---

## 5. Route Predicates

`config.add_route_predicate()` works identically to view predicates but applies during route matching. The predicate factory follows the same protocol.

```python
class SubdomainPredicate:
    def __init__(self, val, config):
        self.subdomain = val

    def text(self):
        return f"subdomain = {self.subdomain}"

    def phash(self):
        return self.text()

    def __call__(self, context, request):
        host = request.host.split(":")[0]
        return host.startswith(f"{self.subdomain}.")

def includeme(config):
    config.add_route_predicate("subdomain", SubdomainPredicate)
```

Usage:

```python
def includeme(config):
    config.add_route("admin.dashboard", "/dashboard", subdomain="admin")
    config.add_route("user.dashboard", "/dashboard", subdomain="app")
```

---

## 6. View Derivers

`config.add_view_deriver()` wraps **all** views with cross-cutting behavior. Unlike tweens (which wrap the entire request pipeline), view derivers wrap individual view callables, giving access to the view's metadata (predicates, renderer, permission).

### Deriver Signature

A view deriver is a function that takes `(view, info)` and returns a new view callable:

```python
def json_error_deriver(view, info):
    """Wrap views to catch exceptions and return JSON error responses."""
    if info.options.get("renderer") != "json":
        return view

    def wrapped(context, request):
        try:
            return view(context, request)
        except AppError as exc:
            request.response.status_int = exc.status_code
            return {"error": exc.error_code, "message": str(exc)}

    return wrapped

def includeme(config):
    config.add_view_deriver(json_error_deriver)
```

### The `info` Object

The `info` parameter provides metadata about the view being wrapped:

- `info.registry` — the application registry
- `info.package` — the package where the view was defined
- `info.settings` — the application settings
- `info.options` — the dict of all options passed to `@view_config` (renderer, permission, etc.)

### Ordering

View derivers form a pipeline, ordered with `under=` and `over=`:

```python
config.add_view_deriver(my_deriver, under="rendered_view", over="mapped_view")
```

Built-in derivers (in order): `INGRESS` → `secured_view` → `owrapped_view` → `http_cached_view` → `rendered_view` → `mapped_view`.

### Derivers vs Tweens

| | Tween | View Deriver |
|---|---|---|
| **Wraps** | Entire request pipeline | Individual view callables |
| **Access to** | `request`, `response` | View callable, view metadata (`info`) |
| **Runs even if** | No view matches (404) | Only when a view is found |
| **Use for** | Request/response transformation, timing | View-specific behavior based on view config |

---

## 7. Static Views

`config.add_static_view()` serves static files (CSS, JS, images) from a directory.

### Basic Usage

```python
def includeme(config):
    config.add_static_view(name="static", path="myapp:static/")
```

This serves files from the `static/` directory inside the `myapp` package at the URL prefix `/static/`. A file at `myapp/static/css/style.css` is served at `/static/css/style.css`.

### URL Generation

Use `request.static_url()` to generate URLs to static files:

```python
css_url = request.static_url("myapp:static/css/style.css")
```

This returns the full URL (e.g., `http://example.com/static/css/style.css`). Using `static_url()` instead of hardcoding paths enables cache-busting and CDN integration.

### Cache Busting

Enable cache busting so browsers fetch updated files when they change:

```python
from pyramid.static import QueryStringCacheBuster

def includeme(config):
    config.add_static_view(name="static", path="myapp:static/")
    config.add_cache_buster("myapp:static/", QueryStringCacheBuster())
```

`QueryStringCacheBuster` appends `?x=<hash>` to static URLs based on file modification time.

### External CDN

For production, serve static files from a CDN by overriding the static view URL:

```python
config.add_static_view(name="https://cdn.example.com/static", path="myapp:static/")
```

Now `request.static_url("myapp:static/style.css")` returns `https://cdn.example.com/static/style.css`.
