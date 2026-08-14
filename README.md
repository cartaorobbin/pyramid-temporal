# pyramid-temporal

[![Release](https://img.shields.io/github/v/release/cartaorobbin/pyramid-temporal)](https://img.shields.io/github/v/release/cartaorobbin/pyramid-temporal)
[![Build status](https://img.shields.io/github/actions/workflow/status/cartaorobbin/pyramid-temporal/main.yml?branch=main)](https://github.com/cartaorobbin/pyramid-temporal/actions/workflows/main.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/cartaorobbin/pyramid-temporal/branch/main/graph/badge.svg)](https://codecov.io/gh/cartaorobbin/pyramid-temporal)
[![Commit activity](https://img.shields.io/github/commit-activity/m/cartaorobbin/pyramid-temporal)](https://img.shields.io/github/commit-activity/m/cartaorobbin/pyramid-temporal)
[![License](https://img.shields.io/github/license/cartaorobbin/pyramid-temporal)](https://img.shields.io/github/license/cartaorobbin/pyramid-temporal)

**pyramid-temporal** provides automatic transaction management for Temporal activities using `pyramid_tm`, exactly how it works for web requests.

This library gives Temporal activities **real Pyramid requests** (built with Pyramid's request factory and request extensions), so all your existing request methods work automatically - `request.dbsession`, `request.tm`, and any other methods configured via `add_request_method`.

- **Github repository**: <https://github.com/cartaorobbin/pyramid-temporal/>
- **Documentation** <https://cartaorobbin.github.io/pyramid-temporal/>

## Features

- **Real Pyramid Requests**: Activities get actual `pyramid.request.Request` objects, not mocks
- **Automatic Transaction Management**: Uses `pyramid_tm` - same as web requests
- **Full Pyramid Integration**: All `add_request_method` configurations work automatically
- **PyramidEnvironment**: Clean wrapper for bootstrap environment with access to app, registry, root
- **Unit of Work Pattern**: Each execution runs in its own transactional scope with a fresh request
- **Safe Concurrency**: Nothing is shared between executions, so `max_concurrent_activities` can be raised
- **Async or Sync Activities**: Write `async def` for cooperative work, or plain `def` to run blocking work in Temporal's activity thread pool
- **Clean Activity Code**: No manual transaction handling or context setup needed
- **Custom Worker**: `pyramid_temporal.Worker` handles activity binding automatically

## Quick Start

### Installation

```bash
pip install pyramid-temporal
```

### Basic Usage

```python
from temporalio import workflow
from temporalio.client import Client
from pyramid_temporal import Worker, activity, ActivityContext, PyramidEnvironment

# Define activities with automatic context injection
@activity.defn
async def enrich_user(context: ActivityContext, user_id: int) -> bool:
    """Activity with full Pyramid integration.
    
    context.request is a REAL Pyramid Request object with all
    configured request methods (dbsession, tm, etc.) available.
    """
    # Access database session - transactions are automatic!
    session = context.request.dbsession
    user = session.query(User).get(user_id)
    
    if user:
        user.enriched = True
        # No need to commit - pyramid_tm handles it on success
        return True
    return False

@activity.defn
async def send_notification(context: ActivityContext, user_id: int, message: str) -> bool:
    """Another activity using context."""
    # Access settings from the real request
    api_key = context.request.registry.settings.get('notification.api_key')
    # ... send notification
    return True

@workflow.defn(sandboxed=False)
class UserOnboardingWorkflow:
    @workflow.run
    async def run(self, user_id: int) -> bool:
        # Enrich user data
        await workflow.execute_activity(
            enrich_user, user_id,
            schedule_to_close_timeout=timedelta(seconds=60)
        )
        # Send welcome notification
        await workflow.execute_activity(
            send_notification, user_id, "Welcome!",
            schedule_to_close_timeout=timedelta(seconds=60)
        )
        return True
```

### Referencing Activities from Workflows

Pass the decorated activity itself, as above, and Temporal resolves it to the
name the `Worker` registered it under. Its registered name works too, which is
handy when the workflow lives in a package that must not import the activity:

```python
await workflow.execute_activity(
    enrich_user, user_id, schedule_to_close_timeout=timedelta(seconds=60)
)
# equivalent
await workflow.execute_activity(
    enrich_user.name, user_id, schedule_to_close_timeout=timedelta(seconds=60)
)
```

Referencing the activity is the better default: the activity's argument and
return types travel with it, so Temporal converts the result back into the type
the activity declared instead of leaving it as plain JSON.

### Blocking Activities

Write the activity as a plain `def` whenever its body blocks - synchronous
database work, HTTP calls, or gRPC calls. Temporal runs sync activities in the
worker's activity thread pool, so a slow or stuck call never occupies the event
loop and never delays the other activities the worker is running:

```python
@activity.defn
def import_orders(context: ActivityContext, batch_id: int) -> int:
    """Blocking body: runs in the activity thread pool, not on the event loop."""
    session = context.request.dbsession
    orders = provider_client.fetch(batch_id)  # blocking gRPC/HTTP is fine here
    session.add_all(orders)
    return len(orders)
```

An `async def` activity still runs on the worker's event loop, so it must only
block cooperatively (`await`). Both flavours receive the same `ActivityContext`.

### Calling an Activity Directly

An activity body is callable, given a context to run in. `activity_execution`
provides one, with the same request and transaction an execution would get, so a
test can exercise the body without a Temporal server:

```python
from pyramid_temporal import activity_execution

def test_import_orders(pyramid_env, batch):
    with activity_execution(pyramid_env, threadlocal_request=True) as context:
        assert import_orders(context, batch.id) == 12
```

An `async def` activity returns its coroutine, for the caller to await.

Register activities with `pyramid_temporal.Worker`, never with
`temporalio.worker.Worker`: only the former binds them to the Pyramid
environment. An activity that reaches Temporal unbound is refused with a
`TypeError` rather than running with no request and no transaction.

### Worker Setup

```python
from pyramid_temporal import Worker, PyramidEnvironment

def create_worker(env: PyramidEnvironment):
    """Create worker with Pyramid integration.

    Args:
        env: PyramidEnvironment from bootstrap (provided by CLI)
    """
    client = env.registry.get('temporal_client')

    # Worker automatically binds activities to the environment
    worker = Worker(
        client,
        env,  # Full Pyramid environment
        task_queue="my-queue",
        activities=[enrich_user, send_notification, import_orders],
        workflows=[UserOnboardingWorkflow],
        max_concurrent_activities=10,
    )
    return worker
```

### Concurrency

Every activity execution owns its `ActivityContext`, its Pyramid request, and
therefore its own `dbsession` and `tm`. Executions share nothing, so
`max_concurrent_activities` can be set as high as your database pool allows.

Two things are worth checking in the application configuration:

- **Use an explicit transaction manager**: set
  `tm.manager_hook = pyramid_tm.explicit_manager` in your settings. Without it,
  `request.tm` falls back to the process-wide `transaction.manager`, which
  concurrent async executions would share on the event loop thread.
- **Size the database pool** for the number of activity slots, since each
  concurrent execution checks out its own connection.

For sync activities the worker creates a `ThreadPoolExecutor` sized to
`max_concurrent_activities` (Temporal's default of 100 when unset). Pass your own
`activity_executor=` to control it yourself.

### Pyramid Configuration

In your Pyramid application, configure as you normally would for web requests:

```python
from pyramid.config import Configurator

def main(global_config, **settings):
    config = Configurator(settings=settings)
    
    # Standard Pyramid/pyramid_tm setup
    config.include('pyramid_tm')
    config.include('pyramid_temporal')
    
    # Configure request.dbsession as you normally would
    config.add_request_method(
        lambda r: get_tm_session(session_factory, r.tm),
        'dbsession',
        reify=True
    )
    
    return config.make_wsgi_app()
```

The same configuration works for both web requests and Temporal activities!

### Starting and Signaling Workflows from Sync Code

Pyramid views and event subscribers run synchronously, but the Temporal client is async.
pyramid-temporal hides the sync->async bridge so you never re-implement `Client.connect` +
`asyncio.run` yourself.

In a view or subscriber, use the request methods (they read connection settings automatically):

```python
def create_reversal_view(request):
    # ... build workflow_input ...
    run_id = request.temporal_start_workflow(
        ReversalWorkflow.run,
        workflow_input,
        id=f"reversal-{reversal_id}",
    )
    # signal a running workflow
    request.temporal_signal_workflow(workflow_id, run_id, "provider_return_received")
```

In request-free code (e.g. a CLI command), use the module-level functions:

```python
from pyramid_temporal import start_workflow, signal_workflow

run_id = start_workflow(
    temporal_host="localhost:7233",
    namespace="default",
    task_queue="payments",
    workflow_run=CreateChargeWorkflow.run,
    arg=workflow_input,
    id=workflow_id,
)

# Pass wait=True to block until the workflow finishes and get its result instead:
result = start_workflow(
    temporal_host="localhost:7233",
    namespace="default",
    task_queue="payments",
    workflow_run=CreateChargeWorkflow.run,
    arg=workflow_input,
    id=workflow_id,
    wait=True,
)
```

Connection settings for the request methods come from the registry:

- `pyramid_temporal.temporal_host` (default `localhost:7233`)
- `pyramid_temporal.temporal_namespace` (default `default`); the alias
  `pyramid_temporal.namespace` is also accepted and takes precedence
- `pyramid_temporal.task_queue` (default `default`); override per call with the
  `task_queue=` keyword

### CLI Usage

Start workers using the CLI command:

```bash
ptemporal-worker development.ini myapp.workers.create_worker
```

## How It Works

Registering an activity binds it to the Pyramid environment. Every call of that
bound activity is one execution, and one execution is one unit of work:

1. **Bootstrap** → `PyramidEnvironment` wraps the full Pyramid bootstrap (app, registry, root)
2. **Activity Starts** → A fresh `ActivityContext` builds a real Pyramid Request with Pyramid's request factory, then applies your `add_request_method` extensions
3. **Transaction Begins** → Using that request's own `request.tm`
4. **Context Injected** → The activity body receives the context and reads `context.request`
5. **Activity Succeeds** → Transaction commits automatically (via `pyramid_tm`)
6. **Activity Fails** → Transaction aborts automatically
7. **Cleanup** → Finished callbacks run and the request is closed

This is exactly how `pyramid_tm` works for web requests - your activities use the same patterns.

### Pyramid threadlocals

`context.request` is the supported way to reach the request, and it works in
every activity. `pyramid.threadlocal.get_current_request()` depends on the
flavour, because Pyramid's threadlocal stack lives on the thread:

| Activity | `get_current_request()` | `get_current_registry()` |
| --- | --- | --- |
| Sync (`def`) | this execution's request | the application registry |
| Async (`async def`) | `None` | the application registry |

A sync activity owns its thread in the activity executor, so its request can be
published there safely. Concurrent async executions share the worker's event loop
thread, where a per-execution request cannot be isolated, so the registry is
published alone rather than handing out another execution's request.

## API Reference

### `@activity.defn`

Decorator to define a pyramid-temporal activity with context injection. Works on
`async def` and on plain `def`:

```python
@activity.defn
async def my_activity(context: ActivityContext, arg1: str, arg2: int) -> bool:
    session = context.request.dbsession
    # ...

@activity.defn
def my_blocking_activity(context: ActivityContext, arg1: str) -> bool:
    session = context.request.dbsession
    # ... blocking work, run in the activity thread pool ...
```

Keyword arguments:

- `name=` - register under a custom activity name (defaults to the function name)
- `no_thread_cancel_exception=` - for sync activities, skip raising the
  cancellation exception inside the activity thread

The decorated activity is what workflow code references, and what a test calls
directly:

- `activity.name` - the name the `Worker` registers it under
- `activity.is_async` - whether the body is a coroutine function
- `workflow.execute_activity(activity, ...)` - resolves to `activity.name`
- `activity(context, *args)` - runs the body inside an existing execution

### `PyramidEnvironment`

Wrapper for the Pyramid bootstrap environment:

```python
from pyramid.paster import bootstrap
from pyramid_temporal import PyramidEnvironment

# Create from bootstrap output
env = PyramidEnvironment.from_bootstrap(bootstrap('development.ini'))

# Access components
env.registry   # Pyramid registry
env.app        # WSGI application
env.request    # Base request object
env.root       # Root object (for traversal)
env.settings   # Shortcut to registry.settings

# Clean up when done
env.close()
```

### `ActivityContext`

Context object passed to activities. One context belongs to one execution, and
accessing `context.request` outside of an execution raises `RuntimeError`:

- `context.env` - Full `PyramidEnvironment`
- `context.registry` - Pyramid registry (shortcut to `env.registry`)
- `context.settings` - Application settings (shortcut to `env.settings`)
- `context.request` - **Real Pyramid Request** with all configured methods:
  - `request.dbsession` - if configured via `add_request_method`
  - `request.tm` - if `pyramid_tm` is included
  - Any other methods you've configured

### `Worker`

Pyramid-aware Temporal worker. Any additional keyword argument is passed
straight to `temporalio.worker.Worker`:

```python
worker = Worker(
    client,                        # Temporal client
    env,                           # PyramidEnvironment (required)
    task_queue="...",              # Task queue name
    activities=[...],              # List of activities
    workflows=[...],               # List of workflows
    max_concurrent_activities=10,  # Safe to raise above 1
)
```

- `worker.env` - the `PyramidEnvironment` activities are bound to
- `worker.task_queue` - the polled task queue
- `worker.activity_executor` - the thread pool the worker created for sync
  activities, or `None` when it created none

### Client helpers

Registered request methods (read connection settings from the registry):

- `request.temporal_start_workflow(workflow_run, arg, *, id, task_queue=None) -> run_id` —
  defaults to the required `pyramid_temporal.task_queue` setting; pass `task_queue=` to
  override for a single call
- `request.temporal_signal_workflow(workflow_id, run_id, signal, *args) -> None`

Request-free functions (for CLIs and scripts):

- `pyramid_temporal.start_workflow(*, temporal_host, namespace, task_queue, workflow_run, arg, id, wait=False) -> run_id`
  — returns the `run_id`; pass `wait=True` to block until the workflow completes and return its result instead
- `pyramid_temporal.signal_workflow(*, temporal_host, namespace, workflow_id, run_id, signal, args=()) -> None`

Both run the async client on a dedicated worker thread, so they are safe to call from
synchronous views, subscribers, and CLI commands.

## Development

See [.dev-local/README.md](.dev-local/README.md) for development setup instructions.

## Inspiration

This library is inspired by [pyramid_tm](https://github.com/Pylons/pyramid_tm), which provides excellent transaction management for Pyramid web applications. We apply the same pattern to Temporal activities.

---

Repository initiated with [fpgmaas/cookiecutter-poetry](https://github.com/fpgmaas/cookiecutter-poetry).
