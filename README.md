# pyramid-temporal

[![Release](https://img.shields.io/github/v/release/cartaorobbin/pyramid-temporal)](https://img.shields.io/github/v/release/cartaorobbin/pyramid-temporal)
[![Build status](https://img.shields.io/github/actions/workflow/status/cartaorobbin/pyramid-temporal/main.yml?branch=main)](https://github.com/cartaorobbin/pyramid-temporal/actions/workflows/main.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/cartaorobbin/pyramid-temporal/branch/main/graph/badge.svg)](https://codecov.io/gh/cartaorobbin/pyramid-temporal)
[![Commit activity](https://img.shields.io/github/commit-activity/m/cartaorobbin/pyramid-temporal)](https://img.shields.io/github/commit-activity/m/cartaorobbin/pyramid-temporal)
[![License](https://img.shields.io/github/license/cartaorobbin/pyramid-temporal)](https://img.shields.io/github/license/cartaorobbin/pyramid-temporal)

**pyramid-temporal** provides automatic transaction management for Temporal activities using `pyramid_tm`, exactly how it works for web requests.

This library gives Temporal activities **real Pyramid requests** (via `pyramid.scripting.prepare`), so all your existing request methods work automatically - `request.dbsession`, `request.tm`, and any other methods configured via `add_request_method`.

- **Github repository**: <https://github.com/cartaorobbin/pyramid-temporal/>
- **Documentation** <https://cartaorobbin.github.io/pyramid-temporal/>

## Features

- **Real Pyramid Requests**: Activities get actual `pyramid.request.Request` objects, not mocks
- **Automatic Transaction Management**: Uses `pyramid_tm` - same as web requests
- **Full Pyramid Integration**: All `add_request_method` configurations work automatically
- **PyramidEnvironment**: Clean wrapper for bootstrap environment with access to app, registry, root
- **Unit of Work Pattern**: Each activity runs in its own transactional scope with fresh request
- **Clean Activity Code**: No manual transaction handling or context setup needed
- **Custom Worker**: `pyramid_temporal.Worker` handles context binding automatically

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

### Worker Setup

```python
from pyramid_temporal import Worker, PyramidEnvironment

def create_worker(env: PyramidEnvironment):
    """Create worker with Pyramid integration.
    
    Args:
        env: PyramidEnvironment from bootstrap (provided by CLI)
    """
    client = env.registry.get('temporal_client')
    
    # Worker automatically binds activities to context
    worker = Worker(
        client,
        env,  # Full Pyramid environment
        task_queue="my-queue",
        activities=[enrich_user, send_notification],
        workflows=[UserOnboardingWorkflow],
    )
    return worker
```

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

### CLI Usage

Start workers using the CLI command:

```bash
ptemporal-worker development.ini myapp.workers.create_worker
```

## How It Works

pyramid-temporal uses `pyramid.scripting.prepare` to give activities real Pyramid requests:

1. **Bootstrap** → `PyramidEnvironment` wraps the full Pyramid bootstrap (app, registry, root)
2. **Activity Starts** → Real Pyramid Request created via `pyramid.scripting.prepare`
3. **Context Injected** → `ActivityContext` provides access to real request with all methods
4. **Activity Succeeds** → Transaction commits automatically (via `pyramid_tm`)
5. **Activity Fails** → Transaction aborts automatically
6. **Cleanup** → Request context closed via `prepare()`'s closer

This is exactly how `pyramid_tm` works for web requests - your activities use the same patterns.

## API Reference

### `@activity.defn`

Decorator to define a pyramid-temporal activity with context injection:

```python
@activity.defn
async def my_activity(context: ActivityContext, arg1: str, arg2: int) -> bool:
    session = context.request.dbsession
    # ...
```

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

Context object passed to activities:

- `context.env` - Full `PyramidEnvironment`
- `context.registry` - Pyramid registry (shortcut to `env.registry`)
- `context.settings` - Application settings (shortcut to `env.settings`)
- `context.request` - **Real Pyramid Request** with all configured methods:
  - `request.dbsession` - if configured via `add_request_method`
  - `request.tm` - if `pyramid_tm` is included
  - Any other methods you've configured

### `Worker`

Pyramid-aware Temporal worker:

```python
worker = Worker(
    client,           # Temporal client
    env,              # PyramidEnvironment (required)
    task_queue="...", # Task queue name
    activities=[...], # List of activities
    workflows=[...],  # List of workflows
)
```

## Development

See [.dev-local/README.md](.dev-local/README.md) for development setup instructions.

## Inspiration

This library is inspired by [pyramid_tm](https://github.com/Pylons/pyramid_tm), which provides excellent transaction management for Pyramid web applications. We apply the same pattern to Temporal activities.

---

Repository initiated with [fpgmaas/cookiecutter-poetry](https://github.com/fpgmaas/cookiecutter-poetry).
