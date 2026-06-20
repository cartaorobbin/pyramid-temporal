# Hypothesis Invariants

Reference for property-based and stateful testing with [hypothesis](https://hypothesis.readthedocs.io/). Loaded from [SKILL.md](SKILL.md) when Phase 1 detects code whose correctness is best expressed as invariants — validators, parsers, numeric calculations, transformations, or stateful components.

The goal of an invariant test is *not* to find one example that works, it is to assert a property that must hold for **every valid input** or **every valid sequence of operations**.

---

## When to reach for hypothesis

Use property invariants when the code under test is:

- A validator (`is_valid_email`, `is_valid_cpf`)
- A parser / serializer pair (`encode` / `decode`, `dumps` / `loads`)
- A numeric calculation with bounds (scores, probabilities, percentages, rates)
- A pure transformation (sort, normalize, deduplicate, project)
- A function with algebraic properties (commutative, associative, idempotent)

Use stateful invariants (`RuleBasedStateMachine`) when the code under test is:

- A small in-memory store, cache, or queue
- A state machine with explicit transitions
- A workflow with ordering rules (e.g., "cannot complete before starting")

Do NOT use hypothesis for:

- Web/HTTP/integration tests (slow, non-deterministic).
- Anything I/O-bound (real DB, real network, file system writes).
- Glue code that mostly delegates to a framework.

---

## Property invariants — patterns

For every property, ask "what *must* be true regardless of the input?". The answer is the assertion. The strategy fills in the input.

The examples below show the imports inline the first time they appear so each block is copy-paste-ready. In a real test file, all imports go at the module top (per the parent skill's `MUST DO`); subsequent tests in the same file reuse them.

### Range / bounds

The output stays inside a known interval.

```python
from hypothesis import given, strategies as st


@given(value=st.floats(allow_nan=False, allow_infinity=False))
def test_score_normalization_stays_in_range(value):
    """Verify normalize_score always returns a value in [0, 1]."""
    result = normalize_score(value)

    assert 0.0 <= result <= 1.0
```

### Round-trip

Decoding the encoded value yields the original.

```python
import json

from hypothesis import given, strategies as st


@given(payload=st.dictionaries(keys=st.text(), values=st.integers()))
def test_dumps_loads_round_trip(payload):
    """Verify json dumps/loads is a round trip for dict[str, int]."""
    assert json.loads(json.dumps(payload)) == payload
```

### Idempotence

Applying the function twice gives the same result as applying it once.

```python
@given(text=st.text())
def test_strip_is_idempotent(text):
    """Verify stripping whitespace is idempotent."""
    once = strip_whitespace(text)
    twice = strip_whitespace(once)

    assert once == twice
```

### Commutativity / associativity

Order of arguments does not change the result.

```python
@given(a=st.integers(), b=st.integers())
def test_merge_metrics_is_commutative(a, b):
    """Verify merge_metrics produces the same value regardless of argument order."""
    assert merge_metrics(a, b) == merge_metrics(b, a)
```

### Monotonicity

If `a <= b`, then `f(a) <= f(b)`. Push the ordering into the strategy with `.map(sorted)` so the test body has no conditional logic.

```python
@given(pair=st.tuples(st.integers(min_value=0), st.integers(min_value=0)).map(sorted))
def test_apply_discount_is_monotonic(pair):
    """Verify apply_discount preserves the order of inputs."""
    a, b = pair

    assert apply_discount(a) <= apply_discount(b)
```

### Type / shape preservation

The result has a known type or shape.

```python
@given(items=st.lists(st.integers()))
def test_sort_preserves_length(items):
    """Verify sort preserves list length."""
    assert len(sort(items)) == len(items)


@given(items=st.lists(st.integers()))
def test_sort_returns_a_list(items):
    """Verify sort returns a list."""
    assert isinstance(sort(items), list)
```

### Validators — accept and reject

Pair an "accepts valid" property with a "rejects invalid" property. Use a custom strategy for the rejection side.

```python
@given(email=st.emails())
def test_email_validator_accepts_valid_emails(email):
    """Verify email validator accepts any valid email format."""
    assert validate_email(email) is True


@given(text=st.text().filter(lambda s: "@" not in s))
def test_email_validator_rejects_strings_without_at(text):
    """Verify email validator rejects strings missing '@'."""
    assert validate_email(text) is False
```

---

## Strategies — quick reference

| Need | Strategy |
|------|----------|
| Bounded integer | `st.integers(min_value=0, max_value=100)` |
| Real number, no NaN/inf | `st.floats(allow_nan=False, allow_infinity=False)` |
| Decimal money | `st.decimals(min_value=0, max_value=10**9, places=2, allow_nan=False, allow_infinity=False)` |
| Non-empty string | `st.text(min_size=1)` |
| String matching a regex | `st.from_regex(r"^[A-Z]{3}\d{4}$", fullmatch=True)` |
| Email | `st.emails()` |
| URL | `st.from_regex(r"^https?://[a-z]+\.com/", fullmatch=True)` |
| List of items | `st.lists(st.integers(), min_size=1, max_size=20)` |
| Dictionary | `st.dictionaries(keys=st.text(), values=st.integers())` |
| Build a domain object | `st.builds(Person, name=st.text(), age=st.integers(0, 120))` |
| Composed strategy | `@composite` decorator |

Composed strategy example:

```python
from hypothesis import strategies as st


@st.composite
def valid_iso_date(draw):
    year = draw(st.integers(min_value=1900, max_value=2100))
    month = draw(st.integers(min_value=1, max_value=12))
    day = draw(st.integers(min_value=1, max_value=28))
    return f"{year:04d}-{month:02d}-{day:02d}"


@given(date_str=valid_iso_date())
def test_parse_iso_date_round_trips(date_str):
    """Verify ISO date parser round-trips through string conversion."""
    parsed = parse_iso_date(date_str)

    assert parsed.isoformat() == date_str
```

---

## Tuning — `@settings`, `@example`, `assume`

- **`@example(...)`** — pin a known regression so hypothesis always tries it. Use after fixing a bug to prevent it from coming back.
- **`@settings(max_examples=N)`** — increase coverage on critical properties; default 100 is fine for most tests.
- **`@settings(deadline=...)`** — extend the per-example deadline only when slowness is intrinsic. Fix slow code instead of widening the deadline whenever possible.
- **`assume(...)`** — drop generated examples that do not satisfy a precondition. Prefer narrowing the strategy directly over filtering after the fact (filters make hypothesis emit `HealthCheck.filter_too_much`).

```python
from hypothesis import example, given, settings, strategies as st


@example(value=0.0)
@example(value=1.0)
@given(value=st.floats(min_value=0.0, max_value=1.0))
@settings(max_examples=500)
def test_score_normalization_at_boundaries(value):
    """Verify score normalization is correct on and near the [0, 1] boundary."""
    result = normalize_score(value)

    assert 0.0 <= result <= 1.0
```

---

## Stateful invariants — `RuleBasedStateMachine`

Use when the code under test is a stateful component and you can describe it with:

- An **initial state** (`@initialize`).
- A small set of **transitions** (`@rule`).
- One or more **invariants** (`@invariant`) that must hold after every transition.

Hypothesis will generate random sequences of rules, run them, and check the invariants. If a sequence breaks an invariant, hypothesis shrinks it to the smallest reproducer.

> **Note on the "no class-based tests" rule.** The parent skill forbids class-based **pytest** tests (e.g., `class TestFoo: def test_method(self): ...`). `RuleBasedStateMachine` is *not* a pytest test class — it is hypothesis's stateful-testing API, exposed to pytest via its `TestCase` attribute. Defining a `RuleBasedStateMachine` subclass and assigning `MyMachine.TestCase` to a module-level name is the documented, idiomatic way to use the API and is the single carve-out from the rule.

### Worked example — counter service

A counter that supports `increment`, `decrement`, and `reset`. Invariants: the count is always a non-negative integer, and `reset` always brings it back to zero.

```python
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from myapp.counters import CounterService


class CounterStateMachine(RuleBasedStateMachine):
    @initialize()
    def setup_counter(self):
        self.counter = CounterService()
        self.expected = 0

    @rule(amount=st.integers(min_value=1, max_value=100))
    def increment(self, amount):
        self.counter.increment(amount)
        self.expected += amount

    @rule(amount=st.integers(min_value=1, max_value=100))
    def decrement(self, amount):
        self.counter.decrement(amount)
        self.expected = max(0, self.expected - amount)

    @rule()
    def reset(self):
        self.counter.reset()
        self.expected = 0

    @invariant()
    def count_is_non_negative(self):
        assert self.counter.value >= 0

    @invariant()
    def count_matches_model(self):
        assert self.counter.value == self.expected


TestCounterStateMachine = CounterStateMachine.TestCase
```

The trailing `TestCase = MyMachine.TestCase` line is the only piece of magic — pytest discovers it like any other test.

### `Bundle` — track generated entities

When rules need to act on entities created by previous rules, use `Bundle` to pass them between rules. Example: a small in-memory store where you `put(key, value)` and later `delete(key)`.

```python
from hypothesis import strategies as st
from hypothesis.stateful import Bundle, RuleBasedStateMachine, initialize, invariant, rule

from myapp.stores import InMemoryStore


class StoreStateMachine(RuleBasedStateMachine):
    keys = Bundle("keys")

    @initialize()
    def setup_store(self):
        self.store = InMemoryStore()
        self.model = {}

    @rule(target=keys, key=st.text(min_size=1, max_size=10), value=st.integers())
    def put(self, key, value):
        self.store.put(key, value)
        self.model[key] = value
        return key

    @rule(key=keys)
    def delete(self, key):
        self.store.delete(key)
        self.model.pop(key, None)

    @rule(key=keys)
    def get_returns_model_value(self, key):
        assert self.store.get(key) == self.model.get(key)

    @invariant()
    def size_matches_model(self):
        assert self.store.size() == len(self.model)


TestStoreStateMachine = StoreStateMachine.TestCase
```

### Tuning state machines

`@settings` works on the `TestCase` attribute of the machine, not on the class itself:

```python
from hypothesis import settings


CounterStateMachine.TestCase.settings = settings(max_examples=200, stateful_step_count=50)
TestCounterStateMachine = CounterStateMachine.TestCase
```

`stateful_step_count` controls how many rules are chained per example (default 50).

---

## Anti-patterns

- **No real I/O inside rules or properties** — no DB writes, no network, no file system. State machines must be deterministic.
- **No `time.sleep` or wall-clock dependencies** — hypothesis runs many examples; sleep makes the suite slow and the failures look like flakes.
- **No shared mutable global state across examples** — set up everything in `@initialize`; teardown by letting the machine go out of scope.
- **No giant state machines** — if a machine has more than ~6 rules, split the system or model only one slice at a time.
- **No `assume(...)` for the bulk of the input space** — narrow the strategy instead.
- **No "happy path only" properties** — pair every "accepts valid" property with a "rejects invalid" property.
- **No conditional logic inside the test body** — push branching into the strategy (use `.map`, `.filter`, `@composite`).
