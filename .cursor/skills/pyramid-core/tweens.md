# Tweens

Pyramid's tween system wraps the entire request/response pipeline with middleware-like behavior. A tween sits between the Pyramid router and the view, intercepting every request and response.

---

## 1. Tween Factory Protocol

A tween factory is a callable that receives `(handler, registry)` and returns a tween callable that receives `(request)` and returns a `Response`:

```python
def timing_tween_factory(handler, registry):
    def timing_tween(request):
        start = time.time()
        response = handler(request)
        duration = time.time() - start
        response.headers["X-Request-Time"] = f"{duration:.4f}"
        return response
    return timing_tween
```

- **`handler`** — the next tween in the chain (or the Pyramid router itself). Call it to continue processing.
- **`registry`** — the application registry. Use it to read settings or access app-wide objects during tween creation.

### Registration

```python
def includeme(config):
    config.add_tween("myapp.tweens.timing_tween_factory")
```

The argument is the dotted Python name of the tween factory, not the factory object itself.

---

## 2. Tween Ordering

Tweens form a chain. The order matters — a tween that catches exceptions must wrap the tweens that might raise them.

### `over=` and `under=`

Position your tween relative to others:

```python
config.add_tween(
    "myapp.tweens.timing_tween_factory",
    under="pyramid_tm.tm_tween_factory",
)
```

- **`under=X`** — run *after* X (closer to the view). X wraps your tween.
- **`over=X`** — run *before* X (closer to the client). Your tween wraps X.

Think of the tween chain as a stack. `over` means higher in the stack (runs first on the way in, last on the way out). `under` means lower (runs later on the way in, earlier on the way out).

### Built-in Tweens

Pyramid has two implicit tweens:

- **`INGRESS`** — the outermost position (closest to the client)
- **`MAIN`** — the innermost position (the Pyramid router itself)

Common third-party tweens and their typical positions:

| Tween | Position | Purpose |
|-------|----------|---------|
| `pyramid_tm.tm_tween_factory` | Near INGRESS | Transaction management (commit/abort) |
| `pyramid.tweens.excview_tween_factory` | Under `pyramid_tm` | Exception view lookup |

### Typical Ordering

```
INGRESS (outermost)
  └─ pyramid_tm (transaction management)
      └─ excview (exception view matching)
          └─ your custom tweens
              └─ MAIN (router → view)
```

### When Position Matters

- **Error handling tweens** should be `over` the tweens that might raise errors, so they can catch them.
- **Transaction tweens** (`pyramid_tm`) should be outermost so they can abort the transaction on any error.
- **Timing tweens** should be `under=INGRESS` to measure the full request lifecycle.
- **If position doesn't matter**, omit `over=` and `under=` — Pyramid places the tween in a sensible default position. Document this assumption.

---

## 3. Common Patterns

### Error Handling

```python
def error_tween_factory(handler, registry):
    def error_tween(request):
        try:
            return handler(request)
        except Exception:
            log.exception("Unhandled exception for %s %s", request.method, request.path)
            raise
    return error_tween
```

### Request Enrichment

```python
def correlation_id_tween_factory(handler, registry):
    def correlation_id_tween(request):
        request.correlation_id = request.headers.get("X-Correlation-ID", str(uuid4()))
        response = handler(request)
        response.headers["X-Correlation-ID"] = request.correlation_id
        return response
    return correlation_id_tween
```

### Conditional Bypass

```python
def auth_tween_factory(handler, registry):
    skip_paths = {"/health", "/ready"}

    def auth_tween(request):
        if request.path in skip_paths:
            return handler(request)
        verify_auth(request)
        return handler(request)
    return auth_tween
```

### Using Registry Settings

```python
def rate_limit_tween_factory(handler, registry):
    max_requests = int(registry.settings.get("rate_limit.max", "100"))
    window = int(registry.settings.get("rate_limit.window", "60"))

    limiter = RateLimiter(max_requests=max_requests, window=window)

    def rate_limit_tween(request):
        if not limiter.allow(request.client_addr):
            raise HTTPTooManyRequests()
        return handler(request)
    return rate_limit_tween
```

---

## 4. Tweens vs Alternatives

| Need | Mechanism | Why |
|------|-----------|-----|
| Wrap every request/response | **Tween** | Runs on every request, even 404s |
| Wrap only matched views | **View deriver** | Access to view metadata, skips unmatched requests |
| Post-response work for a specific view | **Response callback** | Scoped to the view that registers it |
| Observe request lifecycle | **Event subscriber** | Decoupled, no control over response |
| Pre/post processing with return value | **Tween** | Full control over request and response |
| Error handling for all exceptions | **Tween** (over excview) or **exception view** | Tweens catch everything; exception views match specific exceptions |

### Key Differences from View Derivers

- Tweens wrap the **entire pipeline** including routing, traversal, and exception handling.
- View derivers wrap **individual view callables** after routing has found a match.
- Tweens run even when no view matches (404). View derivers only run when a view is found.
- Tweens see the final `Response` object. View derivers see the view's return value before rendering.
