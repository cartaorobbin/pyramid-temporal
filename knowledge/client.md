# Temporal Client Bridge

## Overview

Provides synchronous helpers to start and signal Temporal workflows from sync Pyramid
code (views, event subscribers, CLI commands). Temporal's client is async; these helpers
hide the sync->async bridge so consumers never re-implement `Client.connect` +
`asyncio.run`.

## Design Decisions

- **Dedicated worker thread, fresh loop per call.** `client.py` submits each coroutine to
  a module-level `ThreadPoolExecutor(max_workers=1)` and runs it with `asyncio.run`. This
  solves two problems at once: `asyncio.run` cannot run inside an already-running event
  loop (a caller may have one), and a `temporalio.client.Client` is bound to the loop that
  created it. Connecting and using the client on the same fresh loop, off the caller's
  thread, is the simplest correct approach.
- **Connect per call (no client reuse).** The reified `request.temporal_client` is bound to
  whatever loop connected it (or `None` when deferred), so it cannot be awaited from the
  bridge's loop. Each helper call opens a fresh connection. Trade-off: simplicity and
  correctness over connection reuse. Matches the pattern consumers already used.
- **Two API layers.** Request-free functions (`start_workflow`, `signal_workflow`) for CLI
  code; request methods (`temporal_start_workflow`, `temporal_signal_workflow`, registered
  in `includeme`) for views/subscribers, which resolve connection settings automatically.
- **`wait` is low-level only.** `start_workflow(wait=True)` (execute-and-block) exists on the
  request-free function for CLI/script use. It is intentionally NOT exposed on the
  `temporal_start_workflow` request method: blocking a synchronous web request on a workflow
  result is an anti-pattern, and the only consumer needing it is the CLI.
- **Task queue defaulted in settings, overridable per call.** `includeme` defaults
  `pyramid_temporal.task_queue` to `"default"`. `temporal_start_workflow` injects that
  configured queue when the caller omits `task_queue`, so views/subscribers don't repeat it;
  passing `task_queue=` overrides per call.
- **Namespace key compatibility.** `_client_settings` accepts both
  `pyramid_temporal.namespace` (alias, takes precedence) and
  `pyramid_temporal.temporal_namespace` (canonical, the key `includeme` defaults). This
  avoids forcing `.ini` changes on existing consumers.

## API Surface

- `pyramid_temporal.start_workflow(*, temporal_host, namespace, task_queue, workflow_run, arg, id, wait=False) -> str | Any`
  — connects and starts. Default (`wait=False`) returns `run_id: str` (raises `RuntimeError` if
  Temporal returns no run id). With `wait=True` it blocks until the workflow completes and returns
  its result (via `execute_workflow`). Typed with `@overload` so the default path keeps `-> str`.
- `pyramid_temporal.signal_workflow(*, temporal_host, namespace, workflow_id, run_id, signal, args=()) -> None`
- `request.temporal_start_workflow(workflow_run, arg, *, id, task_queue=None) -> str` — task
  queue defaults to the required `pyramid_temporal.task_queue` setting; pass `task_queue=` to
  override per call.
- `request.temporal_signal_workflow(workflow_id, run_id, signal, *args) -> None`
- `_client_settings(request) -> (host, namespace, task_queue)` — internal settings resolver.
- Settings: `pyramid_temporal.temporal_host`, `pyramid_temporal.temporal_namespace`
  (+ `pyramid_temporal.namespace` alias), `pyramid_temporal.task_queue`. Defaults set in
  `includeme`: host `localhost:7233`, namespace `default`, task_queue `default`.

## Key Learnings / Gotchas

- `WorkflowHandle.first_execution_run_id` is `Optional[str]`; `start_workflow` guards against
  `None` and raises rather than returning a wrong type.
- The bridge runs off-thread, so it does not conflict with a session-scoped pytest event loop
  or with a running request loop.
- Signals to a workflow with no active worker are buffered by Temporal; a running worker is
  not required merely to start or signal.
