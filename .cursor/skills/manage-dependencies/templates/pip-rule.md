---
description: Enforces pip with requirements.txt as the dependency manager for this project
alwaysApply: true
---

# Dependency Management — pip

This project uses **pip** with **requirements.txt** for all dependency management. These rules are non-negotiable.

## REQUIRED commands

| Operation | Command |
|---|---|
| Add dependency | `pip install <package>` then `pip freeze > requirements.txt` |
| Add dev dependency | `pip install <package>` then `pip freeze > requirements-dev.txt` |
| Install from requirements | `pip install -r requirements.txt` |
| Install dev requirements | `pip install -r requirements-dev.txt` |
| Update a package | `pip install --upgrade <package>` then `pip freeze > requirements.txt` |
| Show installed packages | `pip list` |

## FORBIDDEN — never use these

- `poetry add` / `poetry install` / `poetry run` — MUST NOT be used. This is not a Poetry project.
- `uv add` / `uv sync` / `uv run` — MUST NOT be used. This is not a uv project.

## CRITICAL — always update requirements files

After **every** `pip install` or `pip install --upgrade`, you MUST update the requirements file:

```bash
pip freeze > requirements.txt
```

If the project separates dev dependencies, update the appropriate file (`requirements-dev.txt`, `requirements-test.txt`, etc.).

Forgetting this step causes environment drift — the requirements file will not match the actual installed packages.

## Virtual environment

- This project MUST use a virtual environment.
- If `.venv/` or `venv/` exists, activate it before any pip operations.
- If no virtual environment exists, create one:

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
```

- MUST NOT install packages into the system Python.

## Requirements files

- `requirements.txt` MUST be committed to version control.
- If the project uses separate files (`requirements-dev.txt`, etc.), all MUST be committed.
- Pin versions in requirements files (use `pip freeze` output, not loose constraints).

<!-- PRIVATE REGISTRY -->
## Private registry

This project uses a private package registry. When adding private packages:
- The index is configured via `pip.conf`, `PIP_INDEX_URL`, or `PIP_EXTRA_INDEX_URL` environment variables.
- If installs fail with 401/403 errors, the token has likely expired. Use the `codeartifact-auth` skill to refresh credentials.
- MUST NOT hardcode tokens in requirements files. Use environment variables or `pip.conf` for authentication.
<!-- /PRIVATE REGISTRY -->
