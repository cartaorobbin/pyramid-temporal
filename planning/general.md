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

### 6. Testing [TODO]
- [ ] Unit tests for transaction manager
- [ ] Integration tests with mock Temporal activities
- [ ] Test transaction rollback scenarios
- [ ] Test Pyramid integration
- [ ] Test CLI command functionality

### 7. Documentation [TODO]
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
