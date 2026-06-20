---
name: manage-dependencies
description: Reference for managing Python dependencies with uv. Use when adding, removing, or updating packages, troubleshooting install errors, or managing the virtual environment and lock file.
---

# Manage Dependencies (uv)

This project uses **uv** for dependency management.

## Adding dependencies

```bash
# Add a production dependency
uv add <package>

# Add with version constraint
uv add "<package>>=1.2,<2.0"

# Add a dev dependency
uv add --dev <package>

# Add multiple packages at once
uv add <package1> <package2> <package3>
```

After adding, `uv.lock` and `pyproject.toml` are updated automatically.

## Removing dependencies

```bash
# Remove a dependency
uv remove <package>

# Remove a dev dependency
uv remove --dev <package>
```

## Updating dependencies

```bash
# Update a single package to its latest compatible version
uv lock --upgrade-package <package> && uv sync

# Update all packages
uv lock --upgrade && uv sync
```

## Installing from lock file

```bash
# Install all dependencies (respects uv.lock)
uv sync

# Install including dev dependencies (default)
uv sync

# Install without dev dependencies
uv sync --no-dev

# Install from lock file without updating (CI)
uv sync --frozen
```

## Running commands

```bash
# Run a command inside the managed virtual environment
uv run python script.py
uv run pytest
uv run ruff check .
```

## Virtual environment

uv manages `.venv/` automatically. There is no need to create or activate it manually.

```bash
# If you need to inspect the venv
uv run python --version
uv run which python
```

## Lock file hygiene

- `uv.lock` must always be committed.
- Never edit `uv.lock` manually.
- If the lock file gets into a bad state, regenerate it: `uv lock`.
- In CI pipelines, use `uv sync --frozen` to ensure reproducible installs.

## pyproject.toml structure

Dependencies are declared in the standard `[project]` table (PEP 621):

```toml
[project]
dependencies = [
    "httpx>=0.27",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "ruff>=0.5",
]
```

Or using uv's dev dependency group:

```toml
[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "ruff>=0.5",
]
```

## Troubleshooting

### Package not found
- Check the package name is correct on PyPI.
- If it's a private package, ensure credentials are configured (see private registry section below or use the `codeartifact-auth` skill).

### Version conflict
- Run `uv lock` to see the full resolution error.
- Try relaxing version constraints in `pyproject.toml`.

### Stale virtual environment
- Remove and recreate: `rm -rf .venv && uv sync`.

<!-- PRIVATE REGISTRY -->
## Private registry

This project uses a private package registry configured via `UV_EXTRA_INDEX_URL` or `[tool.uv.index]` in `pyproject.toml`.

### Authentication

```bash
# Set via environment variable (preferred)
export UV_EXTRA_INDEX_URL="https://aws:<token>@<domain>.d.codeartifact.<region>.amazonaws.com/pypi/<repo>/simple/"

# Or configure in pyproject.toml (URL only, no credentials)
# [tool.uv.index]
# url = "https://<domain>.d.codeartifact.<region>.amazonaws.com/pypi/<repo>/simple/"
```

### Token refresh

If installs fail with 401/403, the token has expired. Use the `codeartifact-auth` skill to refresh, or manually:

```bash
TOKEN=$(aws codeartifact get-authorization-token \
  --domain <domain> --domain-owner <account-id> \
  --region <region> --query authorizationToken --output text)
```

Then update `UV_EXTRA_INDEX_URL` with the new token.
<!-- /PRIVATE REGISTRY -->
