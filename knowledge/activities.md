# Activity Execution

## Overview

Gives each Temporal activity execution a real Pyramid request and a transaction of
its own. `@activity.defn` marks a function as a pyramid-temporal activity, the
`Worker` binds it to a `PyramidEnvironment`, and every call of the bound activity
is one isolated unit of work. Activities may be `async def` or plain `def`; sync
ones run in Temporal's activity executor.

## Design Decisions

- **The bound wrapper owns the lifecycle, not an interceptor.** `PyramidActivity.bind`
  emits a wrapper whose every invocation creates a fresh `ActivityContext`, so there is no
  worker-wide state to corrupt. Before this, `Worker` held one `ActivityContext` for its
  whole lifetime and a `PyramidTemporalInterceptor` drove `create_request` / `close_request`
  on it, which made `max_concurrent_activities > 1` unsafe: overlapping executions
  overwrote each other's request and the first one to finish reset it to `None`.
  `interceptor.py` was deleted, since nothing was left for it to do.
- **Per-execution instance state instead of contextvars.** One wrapper call equals one
  execution, so a plain instance attribute on a fresh context is already isolated. A
  `ContextVar` would also work (each execution is its own `asyncio.Task`, and Temporal
  copies the context into the activity thread for sync activities), but it is state that
  does not need to exist.
- **Both flavours share one context manager.** `execution.activity_execution(env, *,
  threadlocal_request)` builds the request, begins the transaction, commits on success,
  aborts on exception, and closes the request in `finally`. The async and sync wrappers
  differ only in `await` and in the threadlocal argument, so the unit of work cannot drift
  between them.
- **Sync activities exist for blocking bodies.** `bind` used to always emit `async def`,
  which forced a blocking body onto the worker's event loop. A stuck call there stalls the
  whole worker: Temporal marks the attempt failed server-side when
  `start_to_close_timeout` elapses, but the call keeps running and the retry cannot start.
  A plain `def` activity runs in the activity executor instead.
- **The worker owns the activity executor.** Temporal refuses to register a non-async
  activity without an `activity_executor`, so `Worker` creates a `ThreadPoolExecutor` sized
  to `max_concurrent_activities` (Temporal's default of 100 when unset) and shuts it down
  after `run()` / `__aexit__`. A caller-supplied `activity_executor=` is left alone,
  including its lifetime.
- **Threadlocals only where they can be correct.** Pyramid's `threadlocal.manager` is a
  `threading.local` stack, so it cannot isolate executions that share the event loop
  thread. A sync execution owns its thread and publishes a full `RequestContext`. An async
  execution publishes `RegistryContext` instead: registry only, request `None`. Every
  registry-only entry is identical, so overlapping executions may push and pop in any
  order without corrupting the stack, and `get_current_request()` never returns a foreign
  request.

## API Surface

- `@activity.defn` / `activity.defn(name=..., no_thread_cancel_exception=...)` — returns a
  `PyramidActivity`. Accepts `async def` and `def`. `no_thread_cancel_exception` is
  forwarded to `temporalio.activity.defn` on the sync path only.
- `PyramidActivity.name`, `.fn`, `.is_async`, `.bind(env: PyramidEnvironment) -> Callable`.
  `bind` returns a coroutine function for an async activity and a plain function for a sync
  one, already decorated with `temporalio.activity.defn`.
- `is_pyramid_activity(obj) -> bool` — checks the `_pyramid_temporal_activity` marker,
  which is how `Worker` tells pyramid activities from plain Temporal ones.
- `activity_execution(env, *, threadlocal_request) -> Iterator[ActivityContext]` — the unit
  of work. Exported, so a consumer can run an activity body outside Temporal.
- `ActivityContext(env)` — `.env`, `.registry`, `.settings`, `.request`,
  `.create_request(*, threadlocal_request=True)`, `.close_request()`. `.request` raises
  `RuntimeError` before creation and after closing; `create_request` raises if called twice
  on the same context.
- `RegistryContext(registry)` — `begin()` / `end()`, mirroring Pyramid's `RequestContext`.
- `Worker(client, env, *, task_queue, activities, workflows, interceptors, **kwargs)` —
  `.env`, `.task_queue`, `.activity_executor`, `run()`, `__aenter__` / `__aexit__`. Extra
  kwargs reach `temporalio.worker.Worker`. Plain Temporal activities pass through unbound
  and get no Pyramid request.

## Key Learnings / Gotchas

- **`tm.manager_hook` matters for concurrency.** `pyramid_tm.create_tm` returns the
  process-wide `transaction.manager` when neither `request.environ['tm.manager']` nor the
  `tm.manager_hook` setting is present. That manager is thread-local, so concurrent async
  executions on the event loop thread would share one transaction. Applications running
  concurrent activities should set
  `tm.manager_hook = pyramid_tm.explicit_manager`, which hands every request its own
  manager. Sync activities are less exposed, since each runs on its own thread.
- **A sync activity is created and used in its activity thread.** The wrapper runs in the
  executor thread, so the request, its `dbsession`, the transaction, and the threadlocals
  all belong to that thread. Async activities do all of this on the event loop, which means
  their `tm.begin()` and commit are blocking calls on that loop.
- **Sync activities are not picklable.** `bind` emits a closure, so a `ProcessPoolExecutor`
  cannot be used as `activity_executor`. Thread pools only.
- **`getattr(request, "tm", None)` is the pyramid_tm probe.** No `pyramid_tm` means no
  `request.tm`, and the execution then runs with no transaction management at all rather
  than failing.
- **Temporal's async detection accepts callable instances**, whose `__call__` is a coroutine
  function, which is why `Worker._is_async_activity` checks `type(activity).__call__` too.
  Over-detecting a sync activity only creates an unused thread pool, since a
  `ThreadPoolExecutor` starts threads lazily.
- **The regression tests rely on a rendezvous, not on sleeps.** `tests/app/concurrent.py`
  makes each probe wait for the other, with a timeout, so a worker that serializes
  executions fails the activity instead of quietly passing a timing-based assertion.
