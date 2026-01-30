# Pyramid-Temporal Development Plan

## Objective
Create a bridge between Pyramid and Temporal that implements the Unit of Work pattern for Temporal activities using zope.transaction, similar to how pyramid_tm works for web requests.

## Current Active Tasks

### 1. Environment Setup [COMPLETED]
- [x] Create tools-and-setup.mdc documentation in .cursor/rules/
- [x] Create .envrc file for environment variables
- [x] Create .dev-local directory for development files
- [x] Create setup-dev-env.sh script in .dev-local/
- [x] Update .gitignore to exclude development directories from package
- [x] Setup pyenv and pyenv-virtualenv (pyramid-temporal environment)
- [x] Install Poetry in virtual environment
- [x] Add required dependencies using Poetry
  - temporalio (Temporal Python SDK) ✓
  - transaction (zope.transaction) ✓
  - zope-interface (for interfaces) ✓
  - pyramid (for integration) ✓
- [x] Verify dependencies are correctly installed
- [x] Test basic imports work

### 2. Core Transaction Manager Implementation [COMPLETED]
- [x] Create transaction manager interface (ITransactionManager)
- [x] Implement ZopeTransactionManager class
- [x] Add proper logging and error handling
- [x] Add transaction state checking

### 3. Temporal Activity Interceptor [COMPLETED]
- [x] Implement TransactionalActivityInterceptor
- [x] Hook into Temporal's activity lifecycle
- [x] Handle transaction begin/commit/abort automatically
- [x] Add activity name logging for debugging

### 4. Pyramid Integration [COMPLETED]
- [x] Create includeme function for Pyramid configuration
- [x] Add configuration options (log level)
- [x] Register interceptor as utility for dependency injection
- [x] Provide easy setup for Pyramid applications

### 5. CLI Command Implementation [COMPLETED]
- [x] Add click dependency for CLI support
- [x] Create pyramid_temporal/cli.py module
- [x] Implement ptemporal-worker command
  - Takes Pyramid INI file for application bootstrap
  - Takes Python path to worker factory function
  - Bootstraps Pyramid application with pyramid-temporal integration
  - Dynamically imports and calls worker factory function
  - Starts worker and runs forever
- [x] Add console script entry point to pyproject.toml
- [x] Add comprehensive error handling and logging
- [x] Document worker factory function signature and usage

### 6. Activity Context & Dependency Injection [TODO]

**Goal**: Provide clean dependency injection for activities to access Pyramid registry and request-like objects.

**Desired API**:
```python
from pyramid_temporal import Worker, activity, ActivityContext

@activity.defn
async def enrich_user(context: ActivityContext, user_id: int) -> bool:
    # Access database session via request-like object
    session = context.request.dbsession
    # Access Pyramid registry
    setting = context.registry.settings['my.setting']
    # Access transaction manager
    context.request.tm.commit()
    return True

# Worker handles context binding automatically
worker = Worker(
    client,
    registry,  # Pyramid registry
    task_queue="my-queue",
    activities=[enrich_user],
    workflows=[MyWorkflow],
)
```

**Components to implement**:

#### 6.1 ActivityContext class
- [ ] Create `pyramid_temporal/context.py` module
- [ ] Implement `ActivityContext` class with:
  - `registry` - Pyramid registry reference
  - `request` - Request-like object (created per activity execution)
- [ ] Implement `ActivityRequest` class with:
  - `dbsession` - Database session (created per activity)
  - `tm` - Transaction manager
  - `registry` - Reference to Pyramid registry
  - `settings` - Shortcut to `registry.settings`

#### 6.2 Activity decorator
- [ ] Create `pyramid_temporal/activity.py` module
- [ ] Implement `@activity.defn` decorator that:
  - Marks function as needing context injection
  - Stores original function for later binding
  - Supports `name` parameter like Temporal's decorator

#### 6.3 Custom Worker class
- [ ] Create `pyramid_temporal/worker.py` module
- [ ] Implement `Worker` class that:
  - Wraps `temporalio.worker.Worker`
  - Takes Pyramid registry as required parameter
  - Auto-binds pyramid-temporal activities to context
  - Passes through plain Temporal activities unchanged
  - Includes transaction interceptor automatically

#### 6.4 Update interceptor
- [ ] Modify interceptor to work with new context system
- [ ] Create request/session per activity execution
- [ ] Clean up resources after activity completes

#### 6.5 Update exports
- [ ] Export new classes from `__init__.py`
- [ ] Maintain backward compatibility

**Design decisions**:
1. Session created fresh per activity (like Pyramid request)
2. Support mixed activities (plain Temporal + pyramid-aware)
3. Transaction management integrated into context
4. Worker wrapper for clean API

### 7. Testing [TODO]
- [ ] Unit tests for transaction manager
- [ ] Integration tests with mock Temporal activities
- [ ] Test transaction rollback scenarios
- [ ] Test Pyramid integration
- [ ] Test CLI command functionality
- [ ] Tests for new ActivityContext and Worker

### 8. Documentation [TODO]
- [ ] Usage examples
- [ ] Configuration guide
- [ ] Comparison with pyramid_tm
- [ ] API documentation
- [ ] CLI command documentation

## Key Design Decisions
1. Use Temporal interceptors for automatic transaction management
2. Follow pyramid_tm patterns for consistency
3. Provide clean API that doesn't require manual transaction handling in activities
4. Support both standalone and Pyramid-integrated usage
