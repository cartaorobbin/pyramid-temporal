---
name: quality-assurance
description: Run quality assurance checks on the current chat session — pre-task validation, post-task checklist, and code review. Use when finishing a task, before committing, or when the user asks for a QA review.
---

# Quality Assurance

This skill defines the QA protocol for the project. It can be invoked explicitly ("run QA") or referenced by the dev workflow at key checkpoints.

## A. Chat-Mode Interpretation

The chat-start triage (`.cursor/rules/dev-workflow-activation.mdc`) determines the mode for each conversation:

| Mode | Dev workflow steps | Quality rules |
|------|-------------------|---------------|
| **Full** | All steps (plan, branch, commits, PR, release) | Enforced |
| **Quick** | Skipped | Enforced |

In **both** modes, every code change must satisfy the quality rules in `.cursor/rules/quality.mdc` and the checklists below.

## B. Quality Command Discovery

Before running any checks, discover the project's actual quality commands. Run this discovery once at the start of each chat session (not before every commit). If the Makefile or CI config changes during the session, re-run discovery. Use the first source that yields results:

### 1. Makefile

Check if a `Makefile` exists at the project root. If it does, look for these targets (in preference order): `check`, `lint`, `quality`, `ci`.

- Run `make -n <target>` (dry-run) to confirm the target exists and see what it executes.
- Prefer `check` — it typically bundles lint, test, and format in a single command.
- If the target orchestrates other make targets (e.g., `check: lint test format`), that is fine — `make check` handles it.
- Store the discovered target (e.g., `make check`) as the quality command.

### 2. CI config

If no Makefile or no quality targets are found, scan `.github/workflows/*.yml` and `.github/workflows/*.yaml` for quality commands:

- Look for jobs or steps whose names suggest quality checks (e.g., `lint`, `check`, `quality`, `test`, `ci`, `format`, `type-check`).
- Extract the `run:` commands from those steps — these are the actual commands the project uses in CI.
- Ignore setup steps (checkout, install dependencies, cache) — only collect the verification commands.
- Store the extracted commands as the quality command list.

### 3. Fallback

If neither a Makefile target nor CI config yields commands, fall back to per-language defaults:

- **Python**: `pytest`, `ruff check .`, `black --check .`
- **JavaScript/TypeScript**: `npm test`, `npx eslint .`, `npx prettier --check .`
- **Go**: `go test ./...`, `golangci-lint run`
- **Rust**: `cargo test`, `cargo clippy -- -D warnings`
- **Flutter/Dart**: `flutter test`, `flutter analyze`

## C. Pre-Task Validation

Before writing any code, verify:

1. **Understand the context** — Read relevant source files, tests, and documentation to understand the area being changed.
2. **Check architecture fit** — Confirm the planned change is consistent with the existing design and patterns.
3. **Identify affected tests** — Locate existing tests that cover the area. Know what needs to run after the change.
4. **Check for related docs** — If the project has documentation or knowledge files, note which ones may need updating.

## D. Post-Task Checklist

After completing a change, verify each item before committing. Use the commands discovered in **Section B** — do not guess or use generic examples when project-specific commands are available.

- [ ] **Quality checks pass** — Run the discovered quality command (e.g., `make check`) or the individual commands extracted from CI config. All checks must pass. If a bundled command fails, inspect the output to identify which specific check (test, lint, or format) needs fixing.
- [ ] **Test quality** — New or modified tests follow the project's testing conventions and any installed testing rules.
- [ ] **Type hints** — All new functions and class attributes have type annotations.
- [ ] **No obvious comments** — Comments explain "why", not "what".

### Full-mode only

These additional checks apply when the full dev workflow is active:

- [ ] **Documentation updated** — If the change affects user-facing behavior, update relevant docs.
- [ ] **Knowledge files updated** — If the change reveals non-obvious design decisions or gotchas, update knowledge files (if the project uses them).

## E. Code Review Patterns

When reviewing code (your own or upon request), check for:

### Correctness
- Does the logic handle edge cases?
- Are error conditions handled explicitly, not silently swallowed?
- Are boundary values tested?

### Test Quality
- Each test covers a single behavior
- Tests are deterministic — no conditional logic inside test functions
- Assertions verify expected outcomes explicitly
- Mocks are used only for truly external dependencies
- Follow the project's testing rules for language-specific patterns

### Consistency
- Naming follows project conventions
- New code matches the patterns used in surrounding code
- No duplicated logic that should be extracted

### Common Mistakes
- Missing type hints on new functions
- Stale imports or unused variables
- Tests that pass trivially (always true assertions, unreachable code paths)
- Comments that narrate code instead of explaining intent
