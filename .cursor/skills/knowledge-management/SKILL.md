---
name: knowledge-management
description: Create or update knowledge files for a feature area. Use when the user says "update knowledge", "create knowledge file for X", "document this feature", or after completing a feature that needs knowledge documentation.
---

# Knowledge Management

This skill guides you through creating or updating files in the `knowledge/` directory. Follow the conventions defined in `.cursor/rules/knowledge.mdc`.

## Step 1: Determine the Action

Use AskQuestion:

```
prompt: "What would you like to do?"
options:
  - Create a new knowledge file for a feature area
  - Update an existing knowledge file
  - Review all knowledge files for staleness
```

---

## Creating a New Knowledge File

### Step 2a: Identify the Feature Area

Ask the user which feature area to document, or infer it from the conversation context. The file should be named after the feature area in lowercase with underscores (e.g., `knowledge/billing.md`, `knowledge/auth.md`).

### Step 3a: Explore the Codebase

Read the source code for the feature area thoroughly:
1. Identify the key modules, classes, and functions
2. Trace the main code paths and data flow
3. Note design decisions that are not obvious from the code alone
4. Look for edge cases, gotchas, and non-obvious behaviors

Also read `knowledge/architecture.md` to understand how this area fits into the overall system.

### Step 4a: Draft the Knowledge File

Write the file following this structure:

```markdown
# <Feature Area Name>

<One or two sentences describing what this area does.>

## Design Decisions

<Why it works the way it does. Trade-offs, constraints, alternatives considered. Use a heading per decision if there are several.>

## API Surface

<Key classes, functions, types, and their relationships. Focus on what another developer (or the AI) needs to know to work in this area correctly.>

## Key Learnings / Gotchas

<Non-obvious behaviors, edge cases, things that broke before, common mistakes to avoid.>
```

### Step 5a: Write and Confirm

Write the file to `knowledge/<feature-area>.md`. Tell the user what was created and suggest they review it.

---

## Updating an Existing Knowledge File

### Step 2b: Identify What Changed

Determine which knowledge file needs updating. This can come from:
- The user specifying a file directly
- A feature that was just implemented or modified
- A bug fix that revealed a non-obvious behavior

### Step 3b: Read Current State

Read the existing knowledge file and the relevant source code. Identify which sections are stale or incomplete.

### Step 4b: Rewrite Affected Sections

Update only the sections that need changes. Knowledge files describe the **present state** — rewrite sections entirely rather than appending notes or changelogs. Keep the same structure (Design Decisions, API Surface, Key Learnings / Gotchas).

### Step 5b: Write and Confirm

Write the updated file. Tell the user what was changed and why.

---

## Reviewing All Knowledge Files

### Step 2c: Scan for Staleness

For each file in `knowledge/`:
1. Read the knowledge file
2. Check if the source code it describes has changed significantly since the file was last written
3. Flag files that appear outdated

### Step 3c: Report

Present a summary listing each knowledge file with its status:
- **Current** — the file accurately reflects the source code
- **Needs update** — the source code has diverged; explain what looks stale
- **Missing** — a significant feature area has source code but no knowledge file

Use **AskQuestion** with `allow_multiple: true` to let the user pick which files to update, then follow the update flow above for each.
