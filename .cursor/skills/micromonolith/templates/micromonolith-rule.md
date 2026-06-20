---
description: Micromonolith architecture — domain isolation, composition root, service layer, anti-corruption layer, and authorization model
globs: "**/*.py"
alwaysApply: false
---

# Micromonolith Architecture

A single deployable application composed of isolated domain modules. Each module is a self-contained package that can be extracted into a standalone service without changing its internal structure. The codebase stays monolithic for deployment simplicity while enforcing service-like boundaries at the code level.

## Why This Pattern

- **Gradual extraction** — any module can become a standalone service when the time is right. The boundaries are already in place.
- **Deployment simplicity** — one artifact to build, deploy, and monitor. No inter-service networking, no distributed transactions.
- **Team autonomy** — each domain module has clear ownership boundaries. Teams can work independently within their module.

## Domain Modules

- Each domain is a separate Python package under `src/` with a single entry point function that wires the module into the application.
- Each domain owns its subpackages: `models`, `services`, `views`, `routes`, `schemas`, `tasks`, `clients`.
- **Cross-module imports are forbidden** — modules depend only on the shared composition root, never on each other. This is the rule that makes extraction possible.
- Subpackages within a module may import from each other freely.

## Composition Root

A dedicated package (`main/`) that wires the application together. It is the only place where domain modules are referenced.

- Creates the application, includes shared infrastructure (transaction management, service registry, auth, session), then includes each domain module.
- **Include order matters** — infrastructure first (it registers hooks and directives), then domain modules (they depend on those hooks).
- The composition root must NOT contain business logic, domain-specific routes, or service implementations. It only wires things together.
- Domain modules are never imported directly — they are activated through the framework's include/plugin mechanism.

## Service Layer

Business logic lives in service classes, not in views or models. Services are the bridge between the HTTP layer and the data layer.

- Define an **interface** for each service boundary (e.g., `IChargeService`). Interfaces declare what a service can do without prescribing how.
- Register **factory functions** that create service instances. Factories receive the request context and return a service bound to the current user, session, and transaction.
- Use **named registrations** for provider variants — same interface, different implementations selected by name (e.g., `IPaymentGateway` with names `"itau"`, `"celcoin"`).
- All services receive the current request, which gives them access to the database session, authenticated user, and transaction manager.
- Views resolve services through the framework's dependency injection — never by importing and instantiating directly.

## Anti-Corruption Layer

All external integrations live under a single top-level `third_party/` package at the project root, organized by provider. Each provider is a self-contained directory with everything it needs.

```
third_party/
  {provider}/
    __init__.py
    models.py        # Boundary models (dual IDs)
    client.py         # HTTP/gRPC transport (pure I/O)
    translator.py     # Maps domain <-> provider semantics
```

- **One directory per provider** (`third_party/itau/`, `third_party/celcoin/`, `third_party/dock/`, etc.). Everything for that provider stays together.
- **Translators** implement the domain interface. Their only job is mapping domain semantics to the provider's API and back. No business logic, no domain rules — just the minimal code to bridge the two worlds.
- **Clients** are pure I/O: handle connections, authentication, serialization. No domain knowledge.
- **Dual-identity persistence** — boundary models store both the domain ID (`charge_uuid`) and the provider's external ID (`provider_id`). Neither side leaks its identity scheme into the other.
- Domain code never imports third-party SDKs directly — always through the interface.

## Authorization Model

- Each resource has a **context** that declares who can do what via an access control list (ACL).
- **Permission string convention**: `<module>::<endpoint>::<action>` (e.g., `billing::charge::create`).
- **Wildcard principals**: `*::*::*` for superuser (all permissions), `*::*::read` for read-only across all modules.
- The security layer resolves authentication tokens to a list of principals, then checks principals against the resource's ACL for the requested permission.
- Permission checks are declarative — views declare the required permission, the framework enforces it. Never hardcode permission checks in business logic.

## Module Anatomy

A typical domain module:

```
src/{domain}/
  __init__.py          # Entry point — wires subpackages into the app
  models/
    __init__.py        # Registers all models in this domain
    {entity}.py        # One model per file
  services/
    __init__.py        # Registers service factories
    interfaces.py      # Service interfaces
    {service}.py       # Service implementation
  views/
    ...                # HTTP handlers / API endpoints
  routes/
    __init__.py        # URL route definitions
  schemas/
    ...                # Request/response serialization
  tasks/
    ...                # Background / async tasks
  clients/
    ...                # Internal clients for other services (future extraction)
```

The entry point function in `__init__.py` includes each subpackage that needs to register with the framework, then scans for decorator-based registrations (views, subscribers).
