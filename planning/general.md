# Pyramid-Temporal Development Plan

## Objective
Create a bridge between Pyramid and Temporal that implements the Unit of Work pattern for Temporal activities using zope.transaction, similar to how pyramid_tm works for web requests.

## Current Active Tasks

### 9. PyramidEnvironment Refactoring [COMPLETED]

**Goal**: Wrap the full `pyramid.paster.bootstrap` output in a dedicated `PyramidEnvironment` class to provide future extensibility and cleaner API.

**Background**: Currently, only `registry` is passed from bootstrap to Worker. The bootstrap returns:
- `app`: WSGI application
- `registry`: Pyramid registry
- `request`: Request object
- `root`: Root object (traversal)
- `closer`: Cleanup callable

**Plan**:

#### Step 1: Create `PyramidEnvironment` class in `pyramid_temporal/environment.py`
```python
class PyramidEnvironment:
    """Wrapper for Pyramid bootstrap environment."""
    
    def __init__(
        self,
        registry: Registry,
        app: Optional[Any] = None,
        request: Optional[Any] = None,
        root: Optional[Any] = None,
        closer: Optional[Callable] = None,
    ):
        self._registry = registry
        self._app = app
        self._request = request
        self._root = root
        self._closer = closer
    
    @classmethod
    def from_bootstrap(cls, env: dict) -> "PyramidEnvironment":
        """Create from pyramid.paster.bootstrap output."""
        return cls(
            registry=env["registry"],
            app=env.get("app"),
            request=env.get("request"),
            root=env.get("root"),
            closer=env.get("closer"),
        )
    
    @property
    def registry(self) -> Registry:
        """Get Pyramid registry."""
        return self._registry
    
    @property
    def app(self) -> Optional[Any]:
        """Get WSGI application."""
        return self._app
    
    @property
    def request(self) -> Optional[Any]:
        """Get base request object."""
        return self._request
    
    @property
    def root(self) -> Optional[Any]:
        """Get root object (for traversal)."""
        return self._root
    
    @property
    def settings(self) -> dict:
        """Shortcut to registry.settings."""
        return self._registry.settings
    
    def close(self) -> None:
        """Clean up resources."""
        if self._closer:
            self._closer()
```

#### Step 2: Update `Worker.__init__` signature
- Accept `PyramidEnvironment` instead of `Registry` (no backward compatibility)

```python
def __init__(
    self,
    client: Client,
    env: "PyramidEnvironment",
    *,
    task_queue: str,
    ...
):
    self._env = env
```

#### Step 3: Update `ActivityContext`
- Accept `PyramidEnvironment` instead of just `Registry`
- Expose `env` property for future use

#### Step 4: Update CLI
- Use `PyramidEnvironment.from_bootstrap(env)`
- Pass full environment to worker factory
- Handle `close()` in cleanup

#### Step 5: Update exports in `__init__.py`
- Export `PyramidEnvironment`

#### Step 6: Update tests

**API after change**:
```python
from pyramid_temporal import Worker, activity, ActivityContext, PyramidEnvironment

# Worker factory receives full environment
def create_worker(env: PyramidEnvironment):
    return Worker(
        client,
        env,  # Full environment
        task_queue="my-queue",
        activities=[my_activity],
    )

# Activities can access full environment in future
@activity.defn
async def my_activity(context: ActivityContext, user_id: int) -> bool:
    # context.env.root available for traversal apps
    # context.env.app available if needed
    session = context.request.dbsession
    return True
```

**Questions to resolve**:
- [x] ~~Should we add deprecation warning when `Registry` is passed directly?~~ **No backward compatibility - only accept `PyramidEnvironment`**
- [x] ~~Should `ActivityContext.env` be exposed immediately or wait for use case?~~ **Expose immediately**

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

### 6. Activity Context & Dependency Injection [COMPLETED]
- [x] Create `pyramid_temporal/context.py` with ActivityContext and ActivityRequest classes
- [x] Create `pyramid_temporal/activity.py` with `@activity.defn` decorator
- [x] Create `pyramid_temporal/worker.py` with custom Worker class
- [x] Update interceptor to work with new context system
- [x] Update exports in `__init__.py`
- [x] Update example worker to use new API

**New API**:
```python
from pyramid_temporal import Worker, activity, ActivityContext

@activity.defn
async def my_activity(context: ActivityContext, user_id: int) -> bool:
    session = context.request.dbsession
    user = session.query(User).get(user_id)
    return user is not None

worker = Worker(
    client,
    registry,  # Pyramid registry
    task_queue="my-queue",
    activities=[my_activity],
    workflows=[MyWorkflow],
)
```

### 7. Testing [TODO]
- [ ] Unit tests for transaction manager
- [ ] Integration tests with mock Temporal activities
- [ ] Test transaction rollback scenarios
- [ ] Test Pyramid integration
- [ ] Test CLI command functionality
- [ ] Tests for new ActivityContext and Worker
- [ ] Tests for new ActivityContext and Worker

### 8. Documentation [TODO]
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
