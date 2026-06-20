---
alwaysApply: true
---

# Knowledge Directory

The `knowledge/` directory contains AI-facing living documentation — one markdown file per feature area describing its current state, design decisions, API surface, and gotchas.

## Two Audiences

- **`docs/` and `README.md`** are for humans — developers, users, contributors. Focus on clarity, examples, and getting-started guidance.
- **`knowledge/`** is for the AI — the agent reads these files to understand the codebase. Focus on precision, design decisions, API surface, gotchas, and non-obvious learnings. Conciseness matters more than prose quality.
- Both must stay in sync. When a feature changes, update both.

## Structure

One markdown file per feature area (e.g., `knowledge/auth.md`, `knowledge/billing.md`, `knowledge/architecture.md`). Each file follows a consistent structure:

1. **Overview** — What this area does, in one or two sentences.
2. **Design Decisions** — Why it works the way it does. Trade-offs, constraints, alternatives considered.
3. **API Surface** — Key classes, functions, types, and their relationships.
4. **Key Learnings / Gotchas** — Non-obvious behaviors, edge cases, things that broke before.

## When to Update

- After completing a new feature — create or extend the relevant file.
- After fixing a significant bug that revealed something non-obvious — add to Key Learnings.
- After making an architectural change — update the affected files.

## What Does NOT Belong

- Task lists, progress tracking, or backlog items.
- Changelogs or timestamps — knowledge files describe the present, not the history.
- Documentation for end users — that lives in `docs/`.

## Reading Before Writing

Before making changes to a feature area, read the relevant `knowledge/*.md` file first. It contains context that may affect your approach.
