---
name: fix-bug
description: Fix bugs using a strict TDD workflow. Use when the user reports a bug, asks to fix a bug, debug an issue, or says things like "fix this bug", "this is broken", "test and fix", or "why is this failing". Enforces test-first discipline — a failing test must exist before any fix is applied.
---

# Fix Bug (TDD)

Fix bugs by writing a failing test first, then making the minimal code change to pass it. **No fix is allowed until a failing test proves the bug exists.**

---

## Issue Tracker Access

Phase 0 (creating or linking an issue) and Phase 1 (reading an existing issue) both need a tracker. Detect what is available — only when an issue is actually involved:

1. **GitHub MCP** (preferred): Check if a GitHub MCP server is configured by scanning the mcps folder for a server matching `github` or containing `github` in its name. If found, verify with a `get_me` call.
2. **gh CLI** (fallback): Run `gh auth status` to verify authentication.
3. **Linear MCP**: Check the mcps folder for a server matching `linear` or containing `linear` in its name.

For GitHub, resolve `owner` and `repo` from the git remote:

```bash
git remote get-url origin
```

Skip tracker detection entirely when the bug comes from a direct description and the user opts out of tracking in Phase 0.

---

## Constraints

### MUST DO
- Write a failing test before any fix
- Confirm hypothesis with user before proceeding to code
- Run the broader test suite after the fix
- Make the minimal fix — smallest change that makes the test pass

### MUST NOT DO
- Fix code before a failing test exists (cardinal rule)
- Assert buggy behavior in the test (`assert result == wrong_value`)
- Write overly broad tests that check 10 things at once
- Refactor or improve nearby code during the fix (separate task)
- Confuse test errors (import failures) with test failures (assertion failures)
- Skip running the test — never assume pass/fail from reading code

---

## Phase 0: Track the Work (Issue & Branch)

> **Skip this entire phase** if you are being driven by the dev-workflow skill — it has already created the issue and the branch. Start directly at Phase 1.

When invoked directly (e.g., the user said "fix this bug"), decide whether to track the work before touching code.

### 0.1 Ask whether to track

Use AskQuestion:

```
prompt: "Track this bug with an issue and a feature branch before fixing?"
options:
  - id: track
    label: "Yes — create/link an issue and a branch"
  - id: inplace
    label: "No — fix in place on the current branch"
```

If the user chooses **No**, skip to Phase 1 (use any issue link or description they gave only as context).

### 0.2 Create or link the issue

If the user chose **Yes**, first detect the tracker (see [Issue Tracker Access](#issue-tracker-access)), then:

**The user already referenced an issue** (a GitHub URL/`#<number>`, or a Linear ID like `ENG-123`) — link it and fetch its details for context.

GitHub via MCP:

```
CallMcpTool: server=github, toolName=issue_read
arguments: { "owner": "<owner>", "repo": "<repo>", "issue_number": <number>, "method": "get" }
```

GitHub via CLI:

```bash
gh issue view <number> --json title,body,labels,comments
```

Linear via MCP:

```
CallMcpTool: server=plugin-linear-linear, toolName=get_issue
arguments: { "id": "<issue-id>" }
```

**No issue exists yet** — define a concise title, a description (what is happening, what should happen, how to trigger it), and create it with the `bug` label.

GitHub via MCP:

```
CallMcpTool: server=github, toolName=issue_write
arguments: { "owner": "<owner>", "repo": "<repo>", "method": "create", "title": "<title>", "body": "<description>", "labels": ["bug"] }
```

GitHub via CLI:

```bash
gh issue create --title "<title>" --body "<description>" --label "bug"
```

Linear via MCP (`save_issue` creates when no `id` is passed; `title` and `team` are required). Resolve `team` first — list the available teams and confirm with the user if there is more than one:

```
CallMcpTool: server=plugin-linear-linear, toolName=list_teams
arguments: {}
```

```
CallMcpTool: server=plugin-linear-linear, toolName=save_issue
arguments: { "title": "<title>", "description": "<description>", "team": "<team>", "labels": ["bug"] }
```

Capture the issue number/identifier.

### 0.3 Create the branch

For **Linear**, prefer the git branch name that `get_issue` already returns for the issue — Linear's GitHub integration auto-links branches that match it. For **GitHub**, create a slug from the issue title (lowercase, hyphens, max 40 chars):

```bash
git checkout -b bug/<issue-ref>-<slug>
git push -u origin HEAD
```

Where `<issue-ref>` is the GitHub issue number or the Linear identifier (e.g., `bug/42-login-timeout`, `bug/ENG-123-login-timeout`).

Then continue to Phase 1.

---

## Phase 1: Understand the Bug

Gather enough context to reproduce the problem. Ask the user **one question at a time** if anything is unclear.

### 1.1 Establish the bug context

Use whatever source you have:

- **An issue from Phase 0** (linked or created) — read its title, description, and comments.
- **A direct description, error log, or stack trace** the user provided — use it as-is.

If you reached Phase 1 from the dev-workflow, the issue already exists; fetch it via the [Issue Tracker Access](#issue-tracker-access) method if you need its details.

### 1.2 Extract the bug facts

Regardless of the source, extract these three items:

- **What is happening** — the actual (broken) behavior
- **What should happen** — the expected (correct) behavior
- **How to trigger it** — steps, input, or conditions that reproduce the bug

If any of these are missing from the issue or description, ask the user to clarify.

### 1.3 Read the affected code

Read the source file(s) involved. Trace the execution path from the entry point (route, CLI command, function call) through to where the bug manifests.

### 1.4 Identify the root cause area

Narrow down the specific function, method, or code block that is responsible. State your hypothesis to the user before proceeding:

> "The bug appears to be in `<function>` — it does X when it should do Y because of Z. I'll write a test that proves this."

Wait for the user to confirm or correct the hypothesis.

---

## Phase 2: Discover Test Infrastructure

Before writing the test, understand the project's testing conventions.

### 2.1 Detect the test runner

Look for configuration files that indicate the test framework:

| Signal | Test runner |
|--------|-------------|
| `pytest.ini`, `pyproject.toml [tool.pytest]`, `conftest.py` | pytest |
| `package.json` with `test` script, `jest.config.*`, `vitest.config.*` | jest / vitest |
| `Cargo.toml` | cargo test |
| `go.mod` | go test |
| `mix.exs` | mix test |
| `build.gradle`, `pom.xml` | JUnit |

If multiple signals exist, prefer the one closest to the affected module.

### 2.2 Find existing tests for the module

Search for test files that correspond to the buggy module:

- Same directory (`test_*.py`, `*.test.ts`, `*_test.go`, etc.)
- Mirror directory (`tests/`, `__tests__/`, `spec/`)

### 2.3 Read test conventions

Read 1-2 existing test files to understand:

- Naming patterns (function names, file names)
- Available fixtures, helpers, or test utilities
- How test data is set up (factories, fixtures, builders, inline)
- Import style and organization

Match these conventions when writing the new test.

---

## Phase 3: Write the Failing Test (RED)

This is the critical phase. The test must fail against the current code.

### 3.1 Write the test

Create a test that:

- Asserts the **correct/expected** behavior (not the buggy behavior)
- Is minimal — tests only the specific bug, not unrelated concerns
- Has a descriptive name: `test_<what>_<expected_outcome>` or equivalent for the language
- Follows the project's existing test conventions (from Phase 2)

Place the test in the appropriate test file. If no test file exists for the module, create one following the project's naming convention.

### 3.2 Run the test

Run **only** the new test:

```
<test-runner> <path-to-test-file>::<test-name>
```

### 3.3 Confirm the test fails

**HARD GATE — Do not proceed to Phase 4 until this is satisfied.**

The test MUST fail. Verify:

1. The test **ran** (did not error due to import/syntax issues)
2. The test **failed on the assertion** (not on setup or unrelated errors)
3. The failure message reflects the bug (e.g., "expected 200 but got 500", "expected True but got False")

If the test passes, it does not capture the bug. Go back to 3.1 and rethink:

- Is the hypothesis from Phase 1 correct?
- Is the test exercising the right code path?
- Are the test inputs triggering the buggy condition?

If the test errors (import failure, missing fixture, syntax error), fix the test infrastructure issue and re-run. Do not confuse test errors with test failures.

---

## Phase 4: Fix the Bug (GREEN)

Now — and only now — fix the code.

### 4.1 Make the minimal fix

Change the **smallest amount of code** that makes the failing test pass. Resist the urge to refactor, clean up, or improve nearby code. Those are separate tasks.

### 4.2 Run the test again

Run the same test from Phase 3:

```
<test-runner> <path-to-test-file>::<test-name>
```

### 4.3 Confirm the test passes

The test MUST pass. If it still fails:

- Re-read the failure message
- Adjust the fix
- Re-run

Iterate until the test is green.

---

## Phase 5: Verify No Regressions

### 5.1 Run the broader test suite

Run all tests in the affected module or directory:

```
<test-runner> <path-to-test-directory>
```

If the test suite is small enough, run the full suite. If it is large, run at minimum the tests for the affected module and any closely related modules.

### 5.2 Handle failures

If any existing tests broke:

- Determine if the fix changed correct behavior (the fix is wrong) or if the old test was asserting buggy behavior (the test needs updating)
- Fix the issue and re-run
- Do not suppress or delete existing tests without explaining why to the user

### 5.3 Report results

Tell the user:

- The test that was written and what it verifies
- The fix that was applied and why
- The test suite results (all passing, or any issues found)

---

## Error Recovery

**Cannot reproduce the bug:**
- Ask user for more specific reproduction steps
- Check if the bug is environment-dependent (OS, Python version, DB state)
- Try running with verbose/debug logging enabled
- If still unable to reproduce, tell the user and do not proceed with a speculative fix

**Test passes immediately (doesn't capture the bug):**
- Re-examine the hypothesis — is the root cause correct?
- Check if test inputs actually trigger the buggy code path
- Look for conditional logic that only triggers under specific state
- Go back to Phase 1.4 and revise the hypothesis with the user

**Test errors on setup (not an assertion failure):**
- Fix the infrastructure issue (missing import, fixture, dependency) first
- Re-run to confirm the test now fails on the assertion, not on setup
- Do not confuse a broken test with a failing test

**Fix breaks unrelated tests:**
- Determine if the fix changed correct behavior (fix is wrong) or old test asserted buggy behavior (test needs updating)
- Never silently delete or suppress existing tests
- If unclear, ask the user before modifying existing tests

**Cannot find existing test infrastructure:**
- Check for test configuration in `pyproject.toml`, `package.json`, `Cargo.toml`, etc.
- If no tests exist at all, ask the user which test framework to use
- Create the minimal test setup needed (test file, conftest if Python)
