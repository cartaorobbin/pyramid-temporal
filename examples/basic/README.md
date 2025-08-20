# Basic Pyramid-Temporal Example

This example demonstrates the fundamental usage of pyramid-temporal with the `ptemporal-worker` CLI command.

## What This Example Shows

- How to create a worker factory function
- How to configure pyramid-temporal via INI file
- How to use the `ptemporal-worker` CLI command
- Basic activity with automatic transaction management
- Simple workflow execution

## Files

- **`worker.py`**: Worker factory function and example activities/workflows
- **`development.ini`**: Pyramid configuration for development
- **`README.md`**: This documentation

## Prerequisites

1. **Install pyramid-temporal**:
   ```bash
   cd /path/to/pyramid-temporal
   poetry install
   ```

2. **Start Temporal server**:
   ```bash
   temporal server start-dev
   ```
   This starts a local Temporal server on `localhost:7233` with a web UI at `http://localhost:8233`.

## Running the Example

1. **Start the worker**:
   ```bash
   cd /path/to/pyramid-temporal
   ptemporal-worker examples/basic/development.ini examples.basic.worker.create_worker
   ```

2. **In another terminal, trigger a workflow** (optional):
   ```python
   import asyncio
   from temporalio.client import Client
   
   async def main():
       client = await Client.connect("localhost:7233")
       result = await client.execute_workflow(
           "ExampleWorkflow",
           "Hello World",
           id="example-workflow-1",
           task_queue="example-queue"
       )
       print(f"Result: {result}")
   
   asyncio.run(main())
   ```

## Understanding the Code

### Worker Factory Function

The `create_worker()` function in `worker.py` demonstrates:

```python
def create_worker(registry) -> Worker:
    """Worker factory function for ptemporal-worker command."""
    # Get Temporal client from pyramid registry (created by includeme)
    temporal_client = registry.get('temporal_client')
    
    if not temporal_client:
        raise RuntimeError("Temporal client not found - check your configuration")
    
    # Create worker with pyramid-temporal interceptor
    return Worker(
        temporal_client,
        task_queue="example-queue",
        workflows=[ExampleWorkflow],
        activities=[example_activity],
        interceptors=[PyramidTemporalInterceptor()],  # Automatic transactions!
    )
```

### Key Points

1. **Factory Signature**: Must accept a `registry` parameter (Pyramid registry)
2. **Return Type**: Must return a `temporalio.worker.Worker` instance
3. **Interceptor**: Include `PyramidTemporalInterceptor()` for transaction management
4. **Client Access**: Get the Temporal client from `registry.get('temporal_client')`

### Configuration

The INI file configures:

```ini
# Temporal connection
pyramid_temporal.temporal_host = localhost:7233
pyramid_temporal.log_level = INFO
pyramid_temporal.auto_connect = true
```

### Activity Transaction Management

Activities automatically get transaction management:

```python
@activity.defn
async def example_activity(message: str) -> str:
    # No manual transaction handling needed!
    # Database operations here will be automatically transactional
    logger.info("Processing message: %s", message)
    return f"Processed: {message}"
```

## What Happens When You Run It

1. **Bootstrap**: `ptemporal-worker` loads the INI file and fully bootstraps the Pyramid application
2. **Configuration**: pyramid-temporal is automatically included and configured via the INI file
3. **Client Setup**: Temporal client is created and registered in the Pyramid registry
4. **Worker Creation**: Your factory function is called with the registry
5. **Worker Start**: The worker starts and begins polling for tasks
6. **Cleanup**: When the worker shuts down, the Pyramid environment is properly cleaned up

## Next Steps

- Try modifying the activity to do database operations
- Add more complex workflows
- Experiment with different configuration options
- Check out other examples for more advanced usage

## Troubleshooting

### Common Issues

1. **Temporal server not running**: Make sure `temporal server start-dev` is running
2. **Import errors**: Ensure you're running from the project root directory
3. **Connection errors**: Check that `localhost:7233` is accessible

### Logging

The example includes detailed logging. Check the console output for:
- Pyramid bootstrap messages
- Worker creation and startup
- Activity execution logs

### Testing

You can test without triggering workflows by just starting the worker and checking that it connects successfully.
