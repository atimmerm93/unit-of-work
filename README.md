# Unit Of Work

This project packages a small transaction-management layer around SQLAlchemy sessions.
It is built for applications that want a simple `@transactional` boundary without passing
session objects through every service and DAO call.

It is designed to sit on top of the `python-di-application` package. In practice, this
library is only useful when your application is composed with that DI framework, because
the transactional decorator depends on the container's post-init wrapping step to attach
`SessionAspect` to decorated methods.

The implementation combines three ideas:

- `SessionAspect` opens a session when a transactional method starts, commits on success,
  rolls back on failure, and clears the session from context afterwards.
- `SessionCache` stores the current SQLAlchemy session in a `ContextVar`, so nested calls
  in the same execution context can reuse one transaction safely.
- `SessionProvider` gives DAOs and services access to the current session, but only while
  they are running inside a transactional boundary.

## Why a Unit Of Work?

The unit-of-work pattern defines a clear transaction scope for one business operation.
Instead of every method deciding independently when to open, commit, or roll back a
database session, one outer boundary manages the whole operation.

In practice, that gives you a few useful guarantees:

- all writes performed during one business action participate in the same transaction
- nested service calls reuse the same session instead of creating accidental sub-transactions
- an exception anywhere in the call chain rolls back the whole unit of work
- data access code can stay focused on persistence logic rather than transaction plumbing

In this repository, the transaction boundary is expressed with the `@transactional`
decorator from [`src/unit_of_work/transactional_decorator.py`](/Users/alti/PycharmProjects/UnitOfWork/src/unit_of_work/transactional_decorator.py).
The decorator delegates to `SessionAspect`, which is registered through `python-di-application`
post-init wrapping.

That dependency is important: without `python-di-application` and its
`apply_post_init_wrappers()` integration point, the decorator does not become active in the
intended way. This project is therefore not a general-purpose standalone transaction
decorator. It is an extension for applications that already use that DI container model.

## Purpose Of The Transactional Decorator

The decorator is meant to be applied to service-layer methods that represent a complete
business operation.

When a decorated method is called:

1. if no session is active, `SessionAspect` opens one through the configured session factory
2. it stores that session in `SessionCache`
3. all code reached through that call can resolve the same session through `SessionProvider`
4. if the method returns normally, the session is committed
5. if the method raises, the session is rolled back
6. the context-local session is always cleared afterwards

If a decorated method calls another decorated method, the inner call reuses the already
active session instead of starting a second transaction.

That is the core behavior this project is trying to make easy and explicit.

## Project Structure

- [`src/unit_of_work/session_aspect.py`](/Users/alti/PycharmProjects/UnitOfWork/src/unit_of_work/session_aspect.py):
  transaction boundary implementation
- [`src/unit_of_work/session_cache.py`](/Users/alti/PycharmProjects/UnitOfWork/src/unit_of_work/session_cache.py):
  context-local storage for the active session
- [`src/unit_of_work/session_provider.py`](/Users/alti/PycharmProjects/UnitOfWork/src/unit_of_work/session_provider.py):
  runtime accessor used by DAOs and services
- [`src/unit_of_work/base_dao.py`](/Users/alti/PycharmProjects/UnitOfWork/src/unit_of_work/base_dao.py):
  convenience base class for persistence helpers
- [`src/unit_of_work/session_factory/sqlite_session_factory.py`](/Users/alti/PycharmProjects/UnitOfWork/src/unit_of_work/session_factory/sqlite_session_factory.py):
  SQLite-backed session factory used by the example and tests

## Example

The example lives under [`src/unit_of_work/example`](/Users/alti/PycharmProjects/UnitOfWork/src/unit_of_work/example).

It contains:

- [`orm_model.py`](/Users/alti/PycharmProjects/UnitOfWork/src/unit_of_work/example/orm_model.py):
  a simple `SourceDocument` SQLAlchemy model
- [`source_document_data_operations.py`](/Users/alti/PycharmProjects/UnitOfWork/src/unit_of_work/example/source_document_data_operations.py):
  a small data operation class with a `@transactional` write method
- [`main.py`](/Users/alti/PycharmProjects/UnitOfWork/src/unit_of_work/example/main.py):
  an example composition root using `DIContainer`

The example flow is:

1. register `SessionAspect`, `SessionCache`, `SessionProvider`, and `SQLiteSessionFactory`
   in the DI container
2. register a SQLite config with in-memory storage and model metadata
3. apply the post-init wrappers so the `@transactional` decorator is connected to the aspect
4. call `SourceDocumentDataOperations.create_source_document()`
5. verify with a direct session that the row was written

This shows the intended usage style:

- service/data-operation methods declare transactional boundaries
- DAO-style code resolves the current session indirectly through `SessionProvider`
- the calling code does not manually open, commit, or roll back the session for each method

It also shows the framework dependency clearly: the example only works once the container
has called `apply_post_init_wrappers()`. That step is what turns the declarative
`@transactional` marker into actual runtime behavior.

## Tests

The test suite is intentionally split between smoke-style integration checks and smaller
unit tests.

### Smoke test

[`tests/test_session_smoke.py`](/Users/alti/PycharmProjects/UnitOfWork/tests/test_session_smoke.py)
is the broad end-to-end test.

It wires the real DI container, aspect, cache, session factory, and SQLAlchemy models
together and validates the main behaviors:

- nested transactional methods reuse the same session
- successful writes are committed
- exceptions in nested calls roll back the outer transaction

If someone is new to the project, this is the best file to read first because it shows the
library in realistic use.

### Unit tests

[`tests/test_session_aspect.py`](/Users/alti/PycharmProjects/UnitOfWork/tests/test_session_aspect.py)
isolates `SessionAspect` and verifies commit, rollback, and nested reuse behavior without
bringing in the full DI and database stack.

[`tests/test_session_cache.py`](/Users/alti/PycharmProjects/UnitOfWork/tests/test_session_cache.py)
focuses on `SessionCache` and validates that its `ContextVar` state is isolated across:

- threads
- spawned processes
- sibling `asyncio` tasks

The async tests are written around actual `ContextVar` semantics: a task inherits the
context present when it is created, but later changes remain local to that task and do not
bleed into siblings or back into the parent context.

## Running The Tests

From the repository root:

```bash
.venv/bin/python -m unittest
```

Or run the most relevant modules directly:

```bash
.venv/bin/python -m unittest tests/test_session_smoke.py
.venv/bin/python -m unittest tests/test_session_aspect.py
.venv/bin/python -m unittest tests/test_session_cache.py
```

## Summary

This project is a compact example of using a context-local session plus a transactional
decorator to implement a unit-of-work pattern around SQLAlchemy.

The main point is not just to save boilerplate. It is to make transaction ownership clear:
the outer business operation owns the session, nested calls participate in the same unit of
work, and failures roll the whole thing back consistently.


## Release

To create a new release, run:
```bash
git tag v0.x.y
git push origin v0.x.y
gh release create v0.x.y --title "v0.x.y" --notes "Release notes"
```