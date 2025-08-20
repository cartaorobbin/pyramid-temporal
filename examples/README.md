# Pyramid-Temporal Examples

This directory contains examples demonstrating how to use pyramid-temporal in various scenarios.

## Available Examples

### [Basic Example](./basic/)
Demonstrates the fundamental usage of pyramid-temporal with the `ptemporal-worker` CLI command.

- **Purpose**: Show how to create a simple worker factory and use the CLI
- **Features**: Basic activity with transaction management, simple workflow
- **Files**: Worker factory, development INI configuration, README

## Future Examples

Additional examples planned:

- **Database Integration**: Example with SQLAlchemy and database transactions
- **Advanced Workflows**: Complex workflows with multiple activities
- **Error Handling**: Demonstrating rollback scenarios and error recovery
- **Production Setup**: Production-ready configuration and deployment
- **Testing**: Unit and integration testing examples

## Prerequisites

Before running any examples:

1. Install pyramid-temporal: `poetry install`
2. Start Temporal server: `temporal server start-dev`
3. Follow the individual example READMEs for specific setup

## General Usage Pattern

All examples follow this general pattern:

1. **Worker Factory**: Create a function that takes a Pyramid configurator and returns a Worker
2. **INI Configuration**: Pyramid configuration file with pyramid-temporal settings
3. **CLI Command**: Use `ptemporal-worker` to start the worker

```bash
ptemporal-worker <ini_file> <worker_factory_path>
```

## Getting Help

- Check individual example READMEs for detailed instructions
- See the main project documentation
- Review the CLI help: `ptemporal-worker --help`
