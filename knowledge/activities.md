# Activity Execution

## Overview

Gives each Temporal activity execution a real Pyramid request and a transaction of
its own. `@activity.defn` marks a function as a pyramid-temporal activity, the
`Worker` binds it to a `PyramidEnvironment`, and every call of the bound activity
is one isolated unit of work. Workflow code references the decorated activity itself.
Activities may be `async def` or plain `def`; sync ones run in Temporal's activity
executor.

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
- **The decorated activity is the workflow-facing reference.** `PyramidActivity` carries a
  `__temporal_activity_definition` and a `__call__`, so
  `workflow.execute_activity(my_activity, ...)` resolves to the registered name. Temporal's
  `_start_activity` accepts only a `str` or a callable, and reads `name`, `arg_types` and
  `ret_type` off the definition; what actually runs is still the bound wrapper the worker
  registered, and both carry the same name. Before this, the decorator returned an object
  that was neither, so workflows had to pass `my_activity.name` and only found out at
  runtime, as a workflow task failure.
- **The definition spells out its types instead of letting Temporal infer them.** The
  context argument is injected by the binding and never travels over the wire, so it is
  stripped from `arg_types`. Inference would also be wrong in the other direction:
  `temporalio.common._type_hints_from_func` falls back to `type(obj).__call__` for a
  callable instance, which erases the declared return type, and `ret_type` is what converts
  an activity result back into the type the body declared rather than leaving it as plain
  JSON.
- **The decorator refuses a body that cannot receive the context.** `arg_types[1:]` assumes
  the first parameter is the context, so a body without it would make the definition claim
  one argument fewer than the activity takes, and the mistake would only surface as an
  activity failure. `_check_context_parameter` rejects a signature with no positional
  parameter, and rejects a first parameter annotated as something that is not an
  `ActivityContext`. A first parameter annotated with nothing, or with `Any`, is accepted,
  since it claims nothing to contradict. `Any` is checked for by identity rather than left to
  `isinstance(declared, type)`, which became True for it in Python 3.11 and would otherwise
  make the refusal depend on the interpreter version. Temporal's own refusal of keyword-only
  parameters is deliberately not
  mirrored: `bind` wraps the body in `(*args, **kwargs)`, so a keyword-only parameter with a
  default works today and rejecting it would break working activities.
- **`__call__` refuses a first argument that is not an `ActivityContext`.** Carrying a
  Temporal definition makes the activity registrable with a plain
  `temporalio.worker.Worker`, which would call it with the workflow's arguments and run the
  body with no request and no transaction. The check turns that into a `TypeError` naming
  `pyramid_temporal.Worker`, and still allows the direct call a unit test makes with a
  context from `activity_execution`.
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
- `PyramidActivity(context, *args, **kwargs)` — runs the body inside an execution that
  already exists, returning the coroutine for an async body. Raises `TypeError` when the
  first argument is not an `ActivityContext`.
- `PyramidActivity` carries `__temporal_activity_definition`, which is what
  `workflow.execute_activity(my_activity, ...)` reads. The constant
  `TEMPORAL_ACTIVITY_DEFINITION` holds that attribute name, since spelling the dunder inside
  the class body would mangle it.
- `activity.defn` raises `TypeError` for a body that cannot receive the context: no
  positional parameter at all, or a first parameter annotated as something other than an
  `ActivityContext`.
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
- **An activity's annotations are resolved at decoration time.** Building the definition
  calls `typing.get_type_hints` on the body, so a type that only exists under
  `TYPE_CHECKING` cannot be annotated any more: `_type_hints` turns the `NameError` into a
  `TypeError` naming the activity and the requirement. Before, the body's annotations were
  never resolved, because the activity Temporal saw was the `(*args, **kwargs)` wrapper from
  `bind`, so this can break an import that used to work. It matches what
  `temporalio.activity.defn` does to every plain activity, and the alternative — dropping
  the types — would silently stop converting arguments and results.
- **A workflow that references an activity object cannot use Temporal's sandbox.** The
  reference makes the workflow module import the activity module, and therefore
  pyramid-temporal and Pyramid. Reloading that chain inside the sandbox fails on
  `zope.interface` and, with those modules passed through, on `datetime.utcnow`. This is
  independent of the reference itself: the same workflow fails identically when it schedules
  the activity by name. Every workflow in `tests/app/` is `@workflow.defn(sandboxed=False)`
  for that reason.
- **Two private `temporalio` APIs are load-bearing.** `temporalio.activity._Definition` and
  `temporalio.common._type_hints_from_func` build the workflow-facing definition. There is no
  public way to attach a definition to something other than the function that
  `temporalio.activity.defn` decorates. `tests/test_activity_definition.py` reads the
  definition back through `_Definition.must_from_callable`, which is the exact call
  Temporal's workflow code makes, so a `temporalio` upgrade that moves either one fails
  loudly there instead of at a customer's workflow task.
- **Temporal's async detection accepts callable instances**, whose `__call__` is a coroutine
  function, which is why `Worker._is_async_activity` checks `type(activity).__call__` too.
  Over-detecting a sync activity only creates an unused thread pool, since a
  `ThreadPoolExecutor` starts threads lazily.
- **The regression tests rely on a rendezvous, not on sleeps.** `tests/app/concurrent.py`
  makes each probe wait for the other, with a timeout, so a worker that serializes
  executions fails the activity instead of quietly passing a timing-based assertion.
  Identity checks (`id(request)`, `id(tm)`, `id(session)`) only prove distinct Python
  objects. Isolation is asserted by each probe flushing its row, then querying the
  sibling email during the rendezvous: a shared session would see that flush, independent
  transactions must not. The isolation probes take a second rendezvous after that
  query so neither execution can commit before the other has looked; on the async
  path the event loop would otherwise finish and commit one activity before the
  sibling queries. Independent abort is asserted the same way, except one execution
  raises after the rendezvous; only the other execution's row is committed.
