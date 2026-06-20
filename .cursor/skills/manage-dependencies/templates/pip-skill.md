---
name: manage-dependencies
description: Reference for managing Python dependencies with pip and requirements.txt. Use when adding, removing, or updating packages, troubleshooting install errors, or managing the virtual environment and requirements files.
---

# Manage Dependencies (pip)

This project uses **pip** with **requirements.txt** for dependency management.

## Adding dependencies

```bash
# Activate the virtual environment first
source .venv/bin/activate

# Add a production dependency
pip install <package>
pip freeze > requirements.txt

# Add with version constraint
pip install "<package>>=1.2,<2.0"
pip freeze > requirements.txt

# Add a dev dependency
pip install <package>
pip freeze > requirements-dev.txt

# Add multiple packages at once
pip install <package1> <package2> <package3>
pip freeze > requirements.txt
```

**Important**: always run `pip freeze > requirements.txt` after installing packages.

## Removing dependencies

```bash
# Remove a dependency
pip uninstall <package>
pip freeze > requirements.txt
```

Note: `pip uninstall` does not remove transitive dependencies. If you need a clean environment, recreate the venv and reinstall from requirements.

## Updating dependencies

```bash
# Update a single package
pip install --upgrade <package>
pip freeze > requirements.txt

# Update all packages (use with caution)
pip install --upgrade -r requirements.txt
pip freeze > requirements.txt

# Show outdated packages
pip list --outdated
```

## Installing from requirements

```bash
# Install all production dependencies
pip install -r requirements.txt

# Install dev dependencies (if separate file exists)
pip install -r requirements-dev.txt

# Install with exact versions (recommended for CI)
pip install -r requirements.txt --no-deps
```

## Virtual environment

```bash
# Create a virtual environment
python -m venv .venv

# Activate (macOS/Linux)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate

# Deactivate
deactivate

# Verify you're in the venv
which python  # Should point to .venv/bin/python
```

Always ensure the virtual environment is active before running pip commands.

## Requirements file conventions

This project may use one or more requirements files:

| File | Purpose |
|---|---|
| `requirements.txt` | Production dependencies |
| `requirements-dev.txt` | Development tools (pytest, ruff, etc.) |
| `requirements-test.txt` | Test-only dependencies (if separate from dev) |

All requirements files should contain pinned versions (output of `pip freeze`).

### Splitting production and dev dependencies

If the project uses a single `requirements.txt`, consider splitting:

```bash
# After installing all packages, generate production requirements
pip freeze > requirements.txt

# For dev, maintain manually or use pip-tools
```

## Troubleshooting

### Package not found
- Check the package name is correct on PyPI.
- If it's a private package, ensure the index is configured (see private registry section below or use the `codeartifact-auth` skill).

### Version conflict
- Create a fresh venv and install from scratch to identify the conflict.
- Use `pip install --dry-run <package>` to preview what would change.

### Stale virtual environment
- Remove and recreate: `rm -rf .venv && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.

<!-- PRIVATE REGISTRY -->
## Private registry

This project uses a private package registry configured via pip configuration.

### Authentication

```bash
# Configure via environment variable
export PIP_EXTRA_INDEX_URL="https://aws:<token>@<domain>.d.codeartifact.<region>.amazonaws.com/pypi/<repo>/simple/"

# Or use aws codeartifact login (writes to pip.conf)
aws codeartifact login --tool pip \
  --domain <domain> --domain-owner <account-id> \
  --region <region> --repository <repo>
```

### Token refresh

If installs fail with 401/403, the token has expired. Use the `codeartifact-auth` skill to refresh, or re-run `aws codeartifact login`.
<!-- /PRIVATE REGISTRY -->
