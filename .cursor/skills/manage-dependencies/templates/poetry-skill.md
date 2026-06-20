---
name: manage-dependencies
description: Reference for managing Python dependencies with Poetry. Use when adding, removing, or updating packages, troubleshooting install errors, or managing the virtual environment and lock file.
---

# Manage Dependencies (Poetry)

This project uses **Poetry** for dependency management.

## Adding dependencies

```bash
# Add a production dependency
poetry add <package>

# Add with version constraint
poetry add "<package>>=1.2,<2.0"

# Add a dev dependency
poetry add --group dev <package>

# Add to a custom group
poetry add --group test <package>

# Add multiple packages at once
poetry add <package1> <package2> <package3>
```

After adding, `poetry.lock` and `pyproject.toml` are updated automatically.

## Removing dependencies

```bash
# Remove a production dependency
poetry remove <package>

# Remove a dev dependency
poetry remove --group dev <package>
```

## Updating dependencies

```bash
# Update a single package to its latest compatible version
poetry update <package>

# Update all packages
poetry update

# Show outdated packages
poetry show --outdated
```

## Installing from lock file

```bash
# Install all dependencies (respects poetry.lock)
poetry install

# Install without dev dependencies
poetry install --without dev

# Install only specific groups
poetry install --only main

# Regenerate lock file without upgrading
poetry lock --no-update
```

## Running commands

```bash
# Run a command inside the managed virtual environment
poetry run python script.py
poetry run pytest
poetry run ruff check .

# Activate the venv in current shell
poetry shell
```

## Virtual environment

Poetry creates and manages the virtual environment automatically.

```bash
# See where the venv is located
poetry env info --path

# List all envs for this project
poetry env list

# Remove a venv
poetry env remove <python-version>

# Use a specific Python version
poetry env use python3.12
```

**Tip**: configure `poetry config virtualenvs.in-project true` to create `.venv/` inside the project directory (recommended for consistency with editor tooling).

## Lock file hygiene

- `poetry.lock` must always be committed.
- Never edit `poetry.lock` manually.
- If the lock file gets into a bad state: `rm poetry.lock && poetry lock`.
- If `pyproject.toml` changed but you don't want to upgrade packages: `poetry lock --no-update`.
- In CI pipelines, `poetry install` respects the lock file by default.

## pyproject.toml structure

Dependencies are declared in the Poetry-specific `[tool.poetry]` table:

```toml
[tool.poetry.dependencies]
python = "^3.12"
httpx = "^0.27"
rich = "^13.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.0"
ruff = "^0.5"
black = "^24.0"
```

## Troubleshooting

### Package not found
- Check the package name is correct on PyPI.
- If it's a private package, ensure the source and credentials are configured (see private registry section below or use the `codeartifact-auth` skill).

### Version conflict / SolverProblemError
- Run `poetry update <package> -vvv` for detailed resolution output.
- Try relaxing version constraints in `pyproject.toml`.
- Check for conflicting constraints across dependency groups.

### Stale virtual environment
- Remove and recreate: `poetry env remove python && poetry install`.

### Lock file out of sync
- `poetry lock --no-update` regenerates the lock file from current `pyproject.toml` constraints without upgrading packages.

<!-- PRIVATE REGISTRY -->
## Private registry

This project uses a private package registry configured via Poetry sources.

### Configuration

```bash
# Check current source configuration
poetry config --list | grep -E 'repositories\.|http-basic\.'

# Configure the source URL
poetry config repositories.<source-name> <url>/simple/

# Configure credentials
poetry config http-basic.<source-name> aws <token>
```

The source must also be declared in `pyproject.toml`:

```toml
[[tool.poetry.source]]
name = "<source-name>"
url = "https://<domain>.d.codeartifact.<region>.amazonaws.com/pypi/<repo>/simple/"
priority = "supplemental"
```

### Token refresh

If installs fail with 401/403, the token has expired. Use the `codeartifact-auth` skill to refresh, or manually:

```bash
TOKEN=$(aws codeartifact get-authorization-token \
  --domain <domain> --domain-owner <account-id> \
  --region <region> --query authorizationToken --output text)

poetry config http-basic.<source-name> aws "${TOKEN}"
```
<!-- /PRIVATE REGISTRY -->
