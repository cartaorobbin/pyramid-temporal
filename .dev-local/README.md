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
1. Verify pyenv and pyenv-virtualenv are installed
2. Install Python 3.11.7 if needed
3. Create a virtual environment named "pyramid-temporal"
4. Install Poetry in the virtual environment
5. Install project dependencies
6. Set up pre-commit hooks

## Manual Setup

If you prefer to set up manually, follow the instructions in:
`.cursor/rules/tools-and-setup.mdc`

## Environment Variables

The project uses `.envrc` (in the project root) for environment configuration with direnv.

## Note

These development files are excluded from the built wheel package to keep the distribution clean.
