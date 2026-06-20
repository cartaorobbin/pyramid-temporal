---
description: Enforces Poetry as the sole dependency manager for this project
alwaysApply: true
---

# Dependency Management — Poetry

This project uses **Poetry** for all dependency management. These rules are non-negotiable.

## REQUIRED commands

| Operation | Command |
|---|---|
| Add dependency | `poetry add <package>` |
| Add dev dependency | `poetry add --group dev <package>` |
| Remove dependency | `poetry remove <package>` |
| Install from lock | `poetry install` |
| Update a package | `poetry update <package>` |
| Update all packages | `poetry update` |
| Run a command in venv | `poetry run <command>` |
| Show installed packages | `poetry show` |
| Regenerate lock file | `poetry lock` |

## FORBIDDEN — never use these

- `pip install` — MUST NOT be used. Poetry manages the virtual environment and lock file. Using pip directly will cause the lock file to diverge from the actual environment.
- `pip freeze` — MUST NOT be used. The lock file is `poetry.lock`.
- `uv add` / `uv sync` / `uv run` — MUST NOT be used. This is not a uv project.
- `python -m pip` — MUST NOT be used. Same as `pip install`.
- Manual edits to `poetry.lock` — MUST NOT be done. Use `poetry lock` to regenerate.

## Virtual environment

- Poetry manages the virtual environment automatically.
- MUST NOT create virtual environments manually (`python -m venv`, `virtualenv`, etc.) for this project's dependencies.
- Use `poetry run <command>` to execute commands inside the venv, or `poetry shell` to activate it.

## Lock file

- `poetry.lock` MUST be committed to version control.
- After adding or removing dependencies, Poetry updates the lock file automatically.
- In CI, use `poetry install --no-interaction` to install from the lock file.
- If the lock file is out of sync with `pyproject.toml`, run `poetry lock --no-update` to regenerate without upgrading packages.

<!-- PRIVATE REGISTRY -->
## Private registry

This project uses a private package registry. When adding private packages:
- The source is configured in `pyproject.toml` under `[[tool.poetry.source]]` and credentials via `poetry config http-basic.<source-name>`.
- If installs fail with 401/403 errors, the token has likely expired. Use the `codeartifact-auth` skill to refresh credentials.
- MUST NOT hardcode tokens in `pyproject.toml`. Use `poetry config` for authentication.
<!-- /PRIVATE REGISTRY -->
