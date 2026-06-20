---
description: Pyramid framework implementation — configuration/registry, module system with includeme, pyramid_services, models, Cornice REST, ACL authorization, transactions, request extensions, events, and exception views
globs: "**/*.py"
alwaysApply: false
---

# Pyramid Developer Conventions

Pyramid-specific implementation of the micromonolith architecture. For the architectural principles (domain isolation, composition root, service layer concepts, anti-corruption layer, authorization model), see the **micromonolith** rule. This rule covers how to implement those principles with Pyramid.

All three developer roles share the conventions below. The role determines which *skill* provides detailed guidance — this rule provides the shared foundation.

## Developer Roles

Identify which role you are in based on the task at hand, then reach for the corresponding skill.

### App Developer

You are in this role when:
- Working in or asking about `main/__init__.py` (composition root, WSGI factory, include order)
- Setting up or modifying test infrastructure (`conftest.py`, test fixtures, transaction wiring)
- Writing pshell snippets or production data-fix scripts
- Configuring app-level concerns (auth policy, session factory, `pyramid_tm` setup)
- Deciding which domain packages to include and in what order

Reach for: **pyramid-app** skill

### Plugin Developer

You are in this role when:
- Creating or modifying a domain package *inside the application codebase*
- Writing an `includeme` entry point or subpackage structure within the app
- Defining service interfaces using the app's `BaseService`, registering factories
- Scaffolding REST endpoints (Cornice services, context factories, schemas)
- The code you're writing lives in the same repo as the composition root

Reach for: **pyramid-plugin** skill

### Library Developer

You are in this role when:
- Working in a standalone Python package (its own repo) that provides Pyramid integration
- Designing `includeme` for external consumers who will `config.include()` your library
- Registering custom directives, tweens, request methods, or settings for host apps
- The library must NOT import from or depend on any specific host app's internals

Reach for: **pyramid-library** skill

**When in doubt**: if the code lives in the application repository, default to **Plugin Developer**. The Library Developer role only applies when the package is distributed independently.

## Configuration and Module System

- Every domain package exposes `def includeme(config)` as its sole public entry point. Pyramid calls this when the composition root runs `config.include('package.name')`.
- **Composition root** (`main/__init__.py`) creates the `Configurator`, includes shared infrastructure first (`pyramid_tm`, `pyramid_services`, auth, session factory), then includes each domain package. Include order matters when a package depends on directives or settings registered by an earlier include.
- **Subpackage includes** — within a domain's `includeme`, use `config.include('.models')`, `config.include('.routes')`, `config.include('.services')`, etc. Each subpackage defines its own `includeme` that handles only its concern.
- **`config.scan()` placement** — call at the end of `includeme`, after all `config.include()` calls. Use `ignore=` for subpackages that were explicitly included to avoid double-scanning.
- **Registry as settings store** — access INI settings via `config.registry.settings` during configuration or `request.registry.settings` at runtime. Never read settings at import time.
- **Registry for shared objects** — register app-wide singletons (HTTP clients, caches, feature flags) as attributes on `config.registry` during configuration. Retrieve at runtime via `request.registry`. For service-layer objects with request lifecycle, prefer `pyramid_services` (interface + factory) instead.
- **Built-in directives** — use `config.add_route()`, `config.add_request_method()`, `config.add_directive()`, `config.add_subscriber()`, and extension directives (e.g., `config.register_service_factory()`) inside `includeme`. Never call these at module level.
- **No import-time side effects** — `includeme` is the only activation path. Module-level code must not register routes, services, or configuration. Imports are fine; what must not happen is calling `config.*` directives outside `includeme`. This ensures packages are inert until explicitly included.

## Service Layer (pyramid_services)

Implements the micromonolith service layer pattern using `pyramid_services` and Zope interfaces.

- Define a Zope `Interface` for each service boundary (e.g., `IChargeService(Interface)`).
- Register factories via `config.register_service_factory(factory, IInterface)` in the domain's `services/__init__.py includeme`.
- Use named registrations for provider variants: `config.register_service_factory(factory, IInterface, name=ProviderName.ITAU)`.
- All services subclass `BaseService` (from `main/services.py`), which provides `self.request`, `self.context`, and `self.session` (the SQLAlchemy session).
- Resolve services at runtime with `request.find_service(IInterface)` or `request.find_service(IInterface, name=...)`.

## Models (SQLAlchemy)

- **Dual-ID pattern**: integer `id` as database PK (`autoincrement=True`), separate `uuid` column (`UUID(as_uuid=True)`, `default=generate_uuid`) as the public/business identifier. API responses hide `id` and expose `uuid` as `id`.
- **Base class with audit columns**: the declarative base provides `created_at`, `updated_at`, `created_by`, `updated_by` on every model.
- **One model per file**, organized under `<domain>/models/`. Each domain's `models/__init__.py` has an `includeme` that imports all model modules so SQLAlchemy registers the table mappings.
- **Table naming**: `__tablename__` is snake_case, singular (e.g., `charge`, `financing`, `dda_subscription`).
- **Relationships**: always use `back_populates=`. Use string class names to avoid import cycles. Polymorphic hierarchies use `__mapper_args__` with `polymorphic_on` / `polymorphic_identity`.
- **Never use PG native enums** (`sqlalchemy.Enum` type) — always store as `String`. PG enums are a migration headache: can't add values inside transactions, can't remove values at all. Use Python `StrEnum` for type safety in code, stored as plain strings in the database.

## Cornice REST Services

- Use `cornice.Service` for all REST endpoints.
- Each service has a context factory class with `__acl__` for authorization.
- Set `permission=` on each handler: `@service.get(permission="view")`, `@service.post(permission="write")`.
- Use Marshmallow schemas for request validation and response serialization.
- To scaffold a new service, use the **rest-endpoints** generator from the **pyramid-plugin** skill.

## Authorization (Pyramid ACL)

Implements the micromonolith authorization model using Pyramid's ACL system. For permission string conventions (`<module>::<endpoint>::<action>`) and wildcard principals (`*::*::*`, `*::*::read`), see the **micromonolith** rule.

- Context factories with `__acl__` attribute (class-level list or `def __acl__(self)` method).
- `SecurityPolicy` resolves JWT claims to principals, delegates to `ACLHelper().permits(context, principals, permission)`.
- Never hardcode permission checks in views — use Pyramid's `permission=` parameter on Cornice services.

## Request Extensions

Extend the request object with custom methods and properties using `config.add_request_method()`. Common patterns:

- **Reified properties** (`reify=True`) — lazy, cached per-request (e.g., `request.dbsession`, `request.billing_client`).
- **Callable methods** — take arguments, execute fresh per call (e.g., `request.feature_flag("dark_mode")`).
- **Registry-backed properties** — expose app-wide singletons stored on `config.registry` via a clean request attribute.

For the full API (reify vs property vs callable, registration patterns, combining with registry attributes), see the **pyramid-core** skill.

## Events

Pyramid's event system enables decoupled communication between components. Subscribe to built-in events (`NewRequest`, `NewResponse`, `BeforeRender`, `ApplicationCreated`) or define custom domain events.

- **`@subscriber(EventClass)`** decorator — discovered via `config.scan()`.
- **`config.add_subscriber(callable, EventClass)`** — explicit registration in `includeme`.
- **Custom events** — define event classes, fire with `request.registry.notify(event)`.

Prefer events for cross-cutting side effects (logging, notifications, analytics). Use direct service calls for core domain operations. For the full event system (built-in events, custom events, subscriber predicates), see the **pyramid-core** skill.

## Exception Views

Handle errors at the application level with exception views:

- **`@exception_view_config(context=ExcClass)`** — map specific exceptions to error responses.
- **`@notfound_view_config`** — handle 404s (no route match).
- **`@forbidden_view_config`** — handle 403s (ACL denied).

Define exception views in a dedicated module and scan them from the composition root. For the full API (precedence rules, JSON error responses, interaction with Cornice), see the **pyramid-core** skill.

## Transaction Management

- `pyramid_tm` with explicit manager: `settings["tm.manager_hook"] = "pyramid_tm.explicit_manager"`.
- Never commit manually — `pyramid_tm` handles commit/abort per request lifecycle.
- Session via `request.dbsession` (reified request method, bound to `request.tm`).
- In tests: use doomed transactions that always abort — see the **pyramid-tests** reference in the **pyramid-app** skill.

## Related Skills

- **pyramid-core** — Framework features reference: request methods, custom directives, events, tweens, exception views, view predicates, view derivers, callbacks, renderers, and static views.
- **pyramid-app** — App Developer role: composition root wiring, test infrastructure (conftest, fixtures, transaction wiring, factory-boy, xdist), and pshell snippet generation.
- **pyramid-plugin** — Plugin Developer role: module anatomy, `includeme` patterns, service layer (`pyramid_services`), and REST endpoint scaffolding for domain packages inside the app.
- **pyramid-library** — Library Developer role: designing standalone Pyramid extensions (own repo/package) with `includeme` for external consumers, custom directives, tweens, and testing with a proper app.
