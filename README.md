# pyramid-temporal

[![Release](https://img.shields.io/github/v/release/tomas_correa/pyramid-temporal)](https://img.shields.io/github/v/release/tomas_correa/pyramid-temporal)
[![Build status](https://img.shields.io/github/actions/workflow/status/tomas_correa/pyramid-temporal/main.yml?branch=main)](https://github.com/tomas_correa/pyramid-temporal/actions/workflows/main.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/tomas_correa/pyramid-temporal/branch/main/graph/badge.svg)](https://codecov.io/gh/tomas_correa/pyramid-temporal)
[![Commit activity](https://img.shields.io/github/commit-activity/m/tomas_correa/pyramid-temporal)](https://img.shields.io/github/commit-activity/m/tomas_correa/pyramid-temporal)
[![License](https://img.shields.io/github/license/tomas_correa/pyramid-temporal)](https://img.shields.io/github/license/tomas_correa/pyramid-temporal)

**pyramid-temporal** provides automatic transaction management for Temporal activities using `zope.transaction`, similar to how `pyramid_tm` works for web requests.

This library implements the Unit of Work pattern for Temporal activities, automatically handling transaction lifecycle (begin/commit/abort) without requiring manual transaction management in your activity code.

- **Github repository**: <https://github.com/tomas_correa/pyramid-temporal/>
- **Documentation** <https://tomas_correa.github.io/pyramid-temporal/>

## Features

- 🔄 **Automatic Transaction Management**: Activities automatically get transaction begin/commit/abort
- 🏗️ **Unit of Work Pattern**: Each activity runs in its own transactional scope
- 🔌 **Pyramid Integration**: Easy integration with Pyramid applications via `includeme`
- 📝 **Clean Activity Code**: No need for manual transaction handling in activities
- 🔍 **Comprehensive Logging**: Built-in logging for debugging transaction flow

## Quick Start

### Installation

```bash
pip install pyramid-temporal
```

### Basic Usage

```python
import asyncio
from temporalio import activity, workflow
from temporalio.worker import Worker
from pyramid_temporal import PyramidTemporalInterceptor

@activity.defn
async def my_activity(data: str) -> str:
    # No manual transaction management needed!
    # Transaction is automatically started/committed/aborted
    # Your database operations here will be transactional
    return f"Processed: {data}"

@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self, data: str) -> str:
        return await workflow.execute_activity(
            my_activity, data, schedule_to_close_timeout=60
        )

async def main():
    # Create worker with transaction management
    worker = Worker(
        client,
        task_queue="my-queue",
        workflows=[MyWorkflow],
        activities=[my_activity],
        interceptors=[PyramidTemporalInterceptor()],  # Adds automatic transactions
    )
    await worker.run()
```

### Pyramid Integration

In your Pyramid application:

```python
from pyramid.config import Configurator

def main():
    config = Configurator()
    config.include('pyramid_temporal')  # Registers pyramid-temporal
    # ... rest of your configuration
    return config.make_wsgi_app()
```

## How It Works

pyramid-temporal uses Temporal's interceptor mechanism to automatically wrap activity execution with transaction management:

1. **Activity Starts** → Transaction begins automatically
2. **Activity Succeeds** → Transaction commits automatically  
3. **Activity Fails** → Transaction aborts automatically

This is similar to how `pyramid_tm` manages transactions for web requests, but applied to Temporal activities.

## Development

See [.dev-local/README.md](.dev-local/README.md) for development setup instructions.

## Inspiration

This library is inspired by [pyramid_tm](https://github.com/Pylons/pyramid_tm), which provides excellent transaction management for Pyramid web applications. We apply the same pattern to Temporal activities.

## Releasing a new version



---

Repository initiated with [fpgmaas/cookiecutter-poetry](https://github.com/fpgmaas/cookiecutter-poetry).