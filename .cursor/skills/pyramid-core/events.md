# Events

Pyramid's event system for decoupled communication between components. Subscribers react to events without the emitter knowing who is listening.

---

## 1. Built-in Events

Pyramid fires these events during the request lifecycle:

| Event | When it fires | Attributes |
|-------|--------------|------------|
| `ApplicationCreated` | After `config.make_wsgi_app()` completes | `app` (the WSGI app) |
| `NewRequest` | At the start of every request | `request` |
| `ContextFound` | After traversal finds a context object | `request` (with `request.context` set) |
| `BeforeTraversal` | Before traversal begins | `request` |
| `NewResponse` | After a response is generated | `request`, `response` |
| `BeforeRender` | Before a renderer produces output | `rendering_val` (the dict/value being rendered), plus renderer system values |

### When to Use Each

- **`ApplicationCreated`** — one-time startup tasks: warm caches, verify external service connectivity, log configuration summary.
- **`NewRequest`** — per-request setup: attach timing metadata, initialize request-scoped state, log incoming requests.
- **`ContextFound`** — post-traversal logic: augment the context, load related data based on the resolved context.
- **`BeforeTraversal`** — pre-traversal setup: resolve context-independent request state before the resource tree is walked. Rarely used in URL dispatch applications.
- **`NewResponse`** — post-response processing: log response status, collect metrics, add headers. The subscriber receives the actual response object via `event.response` and modifications take effect. For view-scoped post-processing, use a response callback instead.
- **`BeforeRender`** — inject globals into template rendering: add `request.route_url` helpers, inject user info, add CSRF tokens.

---

## 2. Subscribing to Events

### `@subscriber` Decorator

```python
from pyramid.events import subscriber, NewRequest

@subscriber(NewRequest)
def on_new_request(event):
    event.request.start_time = time.time()
```

The subscriber is discovered when `config.scan()` runs on the module containing it.

### `config.add_subscriber()`

Register subscribers explicitly in `includeme`, without relying on `config.scan()`:

```python
from pyramid.events import NewRequest

def on_new_request(event):
    event.request.start_time = time.time()

def includeme(config):
    config.add_subscriber(on_new_request, NewRequest)
```

### Which to Use

| Approach | When |
|----------|------|
| `@subscriber` decorator | The module is always scanned; the subscriber should always be active |
| `config.add_subscriber()` | Conditional registration, or when the module is not scanned |

---

## 3. Custom Events

Define domain-specific events that modules can fire and other modules can subscribe to.

### Defining an Event

```python
class OrderPlaced:
    def __init__(self, request, order):
        self.request = request
        self.order = order
```

### Firing an Event

```python
def place_order(request, order_data):
    order = create_order(order_data)
    request.registry.notify(OrderPlaced(request, order))
    return order
```

### Subscribing to a Custom Event

```python
@subscriber(OrderPlaced)
def send_confirmation_email(event):
    send_email(
        to=event.order.customer_email,
        subject="Order Confirmed",
        order_id=event.order.uuid,
    )

@subscriber(OrderPlaced)
def update_inventory(event):
    for item in event.order.items:
        decrease_stock(item.product_id, item.quantity)
```

Multiple subscribers can react to the same event. They run in registration order.

### Interface-Based Events

For more formal contracts, define events as Zope interfaces:

```python
from zope.interface import Interface, implementer

class IOrderEvent(Interface):
    """Marker interface for order-related events."""

@implementer(IOrderEvent)
class OrderPlaced:
    def __init__(self, request, order):
        self.request = request
        self.order = order

@implementer(IOrderEvent)
class OrderCancelled:
    def __init__(self, request, order):
        self.request = request
        self.order = order
```

Subscribe to the interface to handle all order events:

```python
@subscriber(IOrderEvent)
def log_order_event(event):
    log.info("Order event: %s for order %s", type(event).__name__, event.order.uuid)
```

---

## 4. Subscriber Predicates

`config.add_subscriber_predicate()` lets subscribers filter which events they receive based on custom criteria.

### Defining a Predicate

A subscriber predicate follows the same protocol as view predicates:

```python
class EventSourcePredicate:
    def __init__(self, val, config):
        self.expected_source = val

    def text(self):
        return f"event_source = {self.expected_source}"

    def phash(self):
        return self.text()

    def __call__(self, event):
        return getattr(event, "source", None) == self.expected_source

def includeme(config):
    config.add_subscriber_predicate("event_source", EventSourcePredicate)
```

### Usage

```python
@subscriber(OrderPlaced, event_source="web")
def handle_web_order(event):
    """Only handles orders placed via the web interface."""
    ...

@subscriber(OrderPlaced, event_source="api")
def handle_api_order(event):
    """Only handles orders placed via the API."""
    ...
```

---

## 5. Events vs Direct Calls

| | Events | Direct service calls |
|---|---|---|
| **Coupling** | Loose — emitter doesn't know subscribers | Tight — caller knows the service |
| **Consumers** | Multiple subscribers, added independently | Single consumer per call |
| **Flow control** | Fire-and-forget, no return value | Synchronous, can return results |
| **Debugging** | Harder to trace (implicit flow) | Easier to trace (explicit call chain) |
| **Use when** | Side effects that shouldn't block the caller (notifications, audit, analytics) | Core business logic where the result matters |

Prefer events for cross-cutting side effects. Prefer direct calls for core domain operations where the caller needs the result or must handle errors.
