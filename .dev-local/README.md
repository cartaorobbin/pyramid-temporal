# Development Environment Files

This directory contains files and scripts for local development that are not shipped with the package.

## Files

- `setup-dev-env.sh` - Automated setup script for local development environment
- `README.md` - This file

## Setup

To set up your local development environment, run:

```bash
./.dev-local/setup-dev-env.sh
```

This script will:
1. Verify uv is installed (`brew install uv` on Apple Silicon)
2. Pin and install Python 3.11.7
3. Install project dependencies with `uv sync`
4. Set up pre-commit hooks

## Manual Setup

If you prefer to set up manually, follow the instructions in:
`.cursor/rules/tools-and-setup.mdc`

## Environment Variables

The project uses `.envrc` (in the project root) for environment configuration with direnv.

## Note

These development files are excluded from the built wheel package to keep the distribution clean.
