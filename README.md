# pyramid-temporal

[![Release](https://img.shields.io/github/v/release/tomas_correa/pyramid-temporal)](https://img.shields.io/github/v/release/tomas_correa/pyramid-temporal)
[![Build status](https://img.shields.io/github/actions/workflow/status/tomas_correa/pyramid-temporal/main.yml?branch=main)](https://github.com/tomas_correa/pyramid-temporal/actions/workflows/main.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/tomas_correa/pyramid-temporal/branch/main/graph/badge.svg)](https://codecov.io/gh/tomas_correa/pyramid-temporal)
[![Commit activity](https://img.shields.io/github/commit-activity/m/tomas_correa/pyramid-temporal)](https://img.shields.io/github/commit-activity/m/tomas_correa/pyramid-temporal)
[![License](https://img.shields.io/github/license/tomas_correa/pyramid-temporal)](https://img.shields.io/github/license/tomas_correa/pyramid-temporal)

**pyramid-temporal** provides automatic transaction management for Temporal activities using `zope.transaction`, similar to how `pyramid_tm` works for web requests.

This library implements the Unit of Work pattern for Temporal activities, automatically handling transaction lifecycle (begin/commit/abort) and providing access to the Pyramid registry and request-like objects within activities.

- **Github repository**: <https://github.com/tomas_correa/pyramid-temporal/>
- **Documentation** <https://tomas_correa.github.io/pyramid-temporal/>

## Features

- **Automatic Transaction Management**: Activities automatically get transaction begin/commit/abort
- **Pyramid Integration**: Full access to Pyramid registry, settings, and utilities in activities
- **Dependency Injection**: Clean `ActivityContext` provides request-like access to database sessions
- **Unit of Work Pattern**: Each activity runs in its own transactional scope with fresh DB session
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
from pyramid_temporal import Worker, activity, ActivityContext

# Define activities with automatic context injection
@activity.defn
async def enrich_user(context: ActivityContext, user_id: int) -> bool:
    """Activity with full Pyramid integration.
    
    The context provides:
    - context.request.dbsession: Database session (fresh per activity)
    - context.request.tm: Transaction manager
    - context.request.settings: Application settings
    - context.registry: Full Pyramid registry access
    """
    # Access database session - transactions are automatic!
    session = context.request.dbsession
    user = session.query(User).get(user_id)
    
    if user:
        user.enriched = True
        # No need to commit - happens automatically on success
        return True
    return False

@activity.defn
async def send_notification(context: ActivityContext, user_id: int, message: str) -> bool:
    """Another activity using context."""
    # Access settings
    api_key = context.request.settings.get('notification.api_key')
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
from pyramid_temporal import Worker

def create_worker(registry):
    """Create worker with Pyramid integration."""
    client = registry.get('temporal_client')
    
    # Worker automatically binds activities to context
    worker = Worker(
        client,
        registry,  # Pyramid registry for context access
        task_queue="my-queue",
        activities=[enrich_user, send_notification],
        workflows=[UserOnboardingWorkflow],
    )
    return worker
```

### Pyramid Configuration

In your Pyramid application:

```python
from pyramid.config import Configurator

def main(global_config, **settings):
    config = Configurator(settings=settings)
    config.include('pyramid_temporal')  # Registers pyramid-temporal
    
    # Register your database session factory
    config.registry['dbsession_factory'] = get_session_factory(engine)
    
    return config.make_wsgi_app()
```

### CLI Usage

Start workers using the CLI command:

```bash
ptemporal-worker development.ini myapp.workers.create_worker
```

## How It Works

pyramid-temporal uses Temporal's interceptor mechanism combined with a custom Worker to provide seamless Pyramid integration:

1. **Activity Starts** → Fresh database session created, transaction begins
2. **Context Injected** → `ActivityContext` provides access to registry, session, settings
3. **Activity Succeeds** → Transaction commits automatically  
4. **Activity Fails** → Transaction aborts automatically
5. **Cleanup** → Database session closed

This mirrors how `pyramid_tm` manages transactions for web requests, but applied to Temporal activities.

## API Reference

### `@activity.defn`

Decorator to define a pyramid-temporal activity with context injection:

```python
@activity.defn
async def my_activity(context: ActivityContext, arg1: str, arg2: int) -> bool:
    session = context.request.dbsession
    # ...
```

### `ActivityContext`

Context object passed to activities:

- `context.registry` - Pyramid registry
- `context.request.dbsession` - SQLAlchemy session (fresh per activity)
- `context.request.tm` - Transaction manager
- `context.request.settings` - Application settings (shortcut to `registry.settings`)

### `Worker`

Pyramid-aware Temporal worker:

```python
worker = Worker(
    client,           # Temporal client
    registry,         # Pyramid registry (required)
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
