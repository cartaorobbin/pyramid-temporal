# Request and Response

Pyramid's extension points for the request object, response handling, error views, and rendering.

---

## 1. Request Methods

`config.add_request_method()` adds methods or properties to every request object in the application.

### Reified Properties

A reified property is created once per request, then cached for the remainder of that request's lifecycle:

```python
def get_billing_client(request):
    settings = request.registry.settings
    return BillingClient(api_key=settings["billing.api_key"])

def includeme(config):
    config.add_request_method(get_billing_client, "billing_client", reify=True)
```

Access in views or services via `request.billing_client`. The first access calls the function; subsequent accesses return the cached result.

Use `reify=True` for objects that:
- Are expensive to create (HTTP clients, database connections)
- Have request-scoped lifecycle (should be created fresh per request)
- Are accessed multiple times during a single request

### Callable Methods

For methods that take arguments or should execute fresh on every call, omit `reify`:

```python
def get_feature_flag(request, flag_name, default=False):
    flags = request.registry.settings.get("feature_flags", {})
    return flags.get(flag_name, default)

def includeme(config):
    config.add_request_method(get_feature_flag, "feature_flag")
```

Access via `request.feature_flag("dark_mode", default=True)`.

### Property vs Method vs Reify

| Style | Registration | Access | When to use |
|-------|-------------|--------|-------------|
| `reify=True` | `add_request_method(fn, "name", reify=True)` | `request.name` | Expensive object, one per request, cached |
| `property=True` | `add_request_method(fn, "name", property=True)` | `request.name` | Computed on every access, no caching |
| Method (default) | `add_request_method(fn, "name")` | `request.name(args)` | Needs arguments, or should run fresh |

### Where to Register

Register request methods in a module's `includeme`. The most common patterns:

- **Infrastructure modules** (`main/request.py`) — app-wide request extensions like `dbsession`, authentication helpers
- **Domain modules** — domain-specific request properties (less common; prefer services for domain logic)
- **Libraries** — `request.mylib_client` for library-provided functionality

---

## 2. Registry Attributes

For app-wide singletons that outlive individual requests (connection pools, caches, HTTP clients), store them on the registry:

```python
def includeme(config):
    settings = config.registry.settings
    pool = create_connection_pool(
        host=settings["redis.host"],
        max_connections=int(settings.get("redis.max_connections", "10")),
    )
    config.registry.redis_pool = pool
```

Access at runtime via `request.registry.redis_pool`.

### Combining with Request Methods

A common pattern is to store the singleton on the registry and expose it via a reified request method:

```python
def get_redis(request):
    return request.registry.redis_pool.get_connection()

def includeme(config):
    settings = config.registry.settings
    config.registry.redis_pool = create_pool(settings["redis.url"])
    config.add_request_method(get_redis, "redis", reify=True)
```

This gives views clean access (`request.redis`) while keeping the pool lifecycle app-wide.

### Registry vs `pyramid_services`

| Use | Mechanism | When |
|-----|-----------|------|
| `config.registry.foo = bar` | Direct attribute | App-wide singletons created once at startup (clients, caches, config objects) |
| `config.register_service_factory(factory, IFoo)` | `pyramid_services` | Per-request objects that need `request` context (services with DB session, auth, etc.) |

Rule of thumb: if it needs `self.request`, use `pyramid_services`. If it's the same object for every request, put it on the registry.

---

## 3. Response Callbacks

`request.add_response_callback()` registers a function that runs after the response is generated but before it's sent to the client. The callback receives both the request and the response:

```python
def audit_log_callback(request, response):
    if response.status_int >= 400:
        log.warning(
            "Error response: %s %s -> %s",
            request.method,
            request.path,
            response.status,
        )

@view_config(route_name="checkout", renderer="json")
def checkout_view(request):
    request.add_response_callback(audit_log_callback)
    return process_checkout(request)
```

### Common Uses

- **Audit logging** — log request/response pairs for compliance
- **Metrics collection** — record response times, status codes
- **Header injection** — add headers based on processing results
- **Cache control** — set cache headers based on response content

### Registration Patterns

Callbacks can be registered from views, services, or tweens. They can also be registered globally via a `NewRequest` event subscriber:

```python
def add_timing_header(request, response):
    if hasattr(request, "_start_time"):
        elapsed = time.time() - request._start_time
        response.headers["X-Response-Time"] = f"{elapsed:.4f}"

def on_new_request(event):
    event.request._start_time = time.time()
    event.request.add_response_callback(add_timing_header)

def includeme(config):
    config.add_subscriber(on_new_request, NewRequest)
```

---

## 4. Finished Callbacks

`request.add_finished_callback()` registers a function that runs after the response has been sent to the client. It receives only the request:

```python
def cleanup_temp_files(request):
    for path in getattr(request, "_temp_files", []):
        os.unlink(path)

@view_config(route_name="export")
def export_view(request):
    path = generate_export_file(request)
    request._temp_files = [path]
    request.add_finished_callback(cleanup_temp_files)
    return FileResponse(path)
```

### Response Callbacks vs Finished Callbacks

| | Response Callback | Finished Callback |
|---|---|---|
| **Runs** | Before response is sent | After response is sent |
| **Receives** | `(request, response)` | `(request,)` |
| **Can modify response** | Yes | No |
| **Use for** | Headers, logging, metrics | Cleanup, async triggers, resource release |

### When to Use Callbacks vs Other Mechanisms

| Need | Mechanism |
|------|-----------|
| Modify every response (headers, wrapping) | Tween |
| Observe request lifecycle globally | Event subscriber (`NewRequest`, `NewResponse`) |
| Post-processing for a specific view | Response callback |
| Cleanup after response is sent | Finished callback |
| Cross-cutting behavior on all views | View deriver |

---

## 5. Exception Views

Exception views handle errors that occur during request processing. Pyramid matches exceptions to views just like it matches URLs to views.

### `@exception_view_config`

The general-purpose decorator for mapping any exception class to a view:

```python
from pyramid.view import exception_view_config

@exception_view_config(renderer="json")
def error_view(exc, request):
    request.response.status_int = 500
    return {
        "error": "internal_server_error",
        "message": "An unexpected error occurred.",
    }
```

Map specific exception classes:

```python
@exception_view_config(context=ValueError, renderer="json")
def validation_error_view(exc, request):
    request.response.status_int = 400
    return {
        "error": "validation_error",
        "message": str(exc),
    }
```

### `@notfound_view_config`

Handles 404 errors when no route matches or a resource is not found:

```python
from pyramid.view import notfound_view_config

@notfound_view_config(renderer="json")
def notfound_view(request):
    request.response.status_int = 404
    return {
        "error": "not_found",
        "message": f"Resource not found: {request.path}",
    }
```

With `append_slash=True`, Pyramid will try adding a trailing slash before returning 404:

```python
@notfound_view_config(renderer="json", append_slash=True)
def notfound_view(request):
    request.response.status_int = 404
    return {"error": "not_found"}
```

### `@forbidden_view_config`

Handles 403 errors when ACL authorization denies access:

```python
from pyramid.view import forbidden_view_config

@forbidden_view_config(renderer="json")
def forbidden_view(request):
    if not request.authenticated_userid:
        request.response.status_int = 401
        return {"error": "unauthorized", "message": "Authentication required."}
    request.response.status_int = 403
    return {"error": "forbidden", "message": "Insufficient permissions."}
```

### Precedence Rules

1. The most specific exception class wins — `ValueError` beats `Exception`.
2. Exception views are matched using normal view lookup, so predicates (like `request_method`) can further specialize them.
3. Exception views registered later (via `config.include()` order) override earlier ones for the same exception class.

### Exception Views and Cornice

Cornice has its own error handling for schema validation failures. App-level exception views handle errors that escape Cornice's pipeline — uncaught exceptions, authorization failures, and 404s. They coexist without conflict.

### Placement

Exception views should be defined in a dedicated module (e.g., `main/views/errors.py`) and scanned from the composition root. See the **pyramid-app** skill for composition root placement guidance.

---

## 6. Custom Renderers

`config.add_renderer()` registers a renderer factory for a given name. Views specify the renderer via `renderer=` on their decorator.

### Renderer Factory Protocol

A renderer factory receives `(info)` and returns a callable `(value, system) -> str`:

```python
class CSVRendererFactory:
    def __init__(self, info):
        pass

    def __call__(self, value, system):
        request = system["request"]
        request.response.content_type = "text/csv"

        output = io.StringIO()
        writer = csv.writer(output)

        if value:
            writer.writerow(value[0].keys())
            for row in value:
                writer.writerow(row.values())

        return output.getvalue()

def includeme(config):
    config.add_renderer("csv", CSVRendererFactory)
```

Usage in a view:

```python
@view_config(route_name="export", renderer="csv")
def export_view(request):
    return [
        {"name": "Alice", "amount": 100},
        {"name": "Bob", "amount": 200},
    ]
```

### Overriding the Default JSON Renderer

To customize JSON serialization (e.g., handle `datetime`, `Decimal`, `UUID`):

```python
from pyramid.renderers import JSON

def includeme(config):
    json_renderer = JSON()
    json_renderer.add_adapter(datetime, lambda obj, req: obj.isoformat())
    json_renderer.add_adapter(Decimal, lambda obj, req: str(obj))
    json_renderer.add_adapter(UUID, lambda obj, req: str(obj))
    config.add_renderer("json", json_renderer)
```

This replaces the built-in JSON renderer globally. All views with `renderer="json"` benefit automatically.
