# Backend-Specific Rules (Pyramid / Cornice / SQLAlchemy)

Apply these rules when reviewing Python backend files that use Pyramid, Cornice, SQLAlchemy, or Marshmallow.

## 🔴 Critical

- **`DateTime()` without `timezone=True`**: any timestamp column declared as `DateTime()` instead of `DateTime(timezone=True)` must be replaced immediately. Postgres needs `TIMESTAMP WITH TIME ZONE` to store UTC correctly.

  ```python
  # ❌
  created_at = Column(DateTime(), server_default=func.now())

  # ✅
  created_at = Column(DateTime(timezone=True), server_default=func.now())
  ```

- **Timestamp set manually in the application layer**: `created_at` and `updated_at` must use `server_default=func.now()` and `onupdate=func.now()`. Never assign these fields in Python code — Postgres owns these values.

- **FK crossing module boundaries**: a `ForeignKey` referencing a table from a *different* module creates structural coupling. Cross-module references must be a plain `uuid` column with no FK declared.

  ```python
  # ❌ — FK crossing from billing → partners
  partner_id = Column(Integer, ForeignKey("partners.partner.id"))

  # ✅ — logical reference via UUID, no FK
  partner_uuid = Column(UUID(as_uuid=True), nullable=False)
  ```

- **Single Table Inheritance**: any model that stores multiple roles/subtypes in a single table with nullable columns is STI and must be refactored to Joined Table Inheritance.

- **Wrong auth HTTP status code**: missing or invalid credentials must return **401 Unauthorized**. Authenticated but insufficient permissions must return **403 Forbidden**. Never invert these.

- **`id` exposed in API responses or URLs**: the integer `id` is DB-internal only. All public identifiers in responses, tokens, and URLs must use `uuid`.

- **Business logic inside a Cornice view**: views must only parse the request, call the service, and return a response. Business rules and state transitions belong in the service layer, not in the view.

## 🟡 Important

- **Model missing `id` + `uuid`**: every model must have both `id` (int, DB-internal) and `uuid` (UUID v4, public). Models with only one identifier violate the project contract.

- **Marshmallow schema not validating required fields**: schemas that accept `load(partial=True)` by default or use `missing=None` on required fields silently swallow missing data. Required fields must raise `ValidationError` when absent.

- **Partial assertions in tests**: tests must assert the complete response body. `assert "key" in response.json` is insufficient — it lets schema regressions pass silently.

  ```python
  # ❌
  assert "access_token" in response.json

  # ✅
  assert response.json == {"access_token": ANY, "token_type": "bearer"}
  ```

- **AAA pattern missing in tests**: every test must follow Arrange / Act / Assert, with each block separated by a blank line and labeled with `# Arrange`, `# Act`, `# Assert` (or `# Act & Assert`).

- **Overlapping coverage between test layers**: each layer tests what is unique to its scope — never duplicate the same verification across layers. Unit tests cover business rules (validations, normalizations, exceptions). Functional tests cover the API contract (HTTP status, full response shape, auth guards, complete HTTP → DB → HTTP flow). If a service method just delegates to the repository with no logic, it does **not** need a unit test — the functional test already covers the flow.

  ```python
  # ❌ useless unit test — pass-through, no logic
  def test_get_partner_happy_path():
      repo = mock_repo(_make_partner())
      result = PartnerService(repo).get(uuid)
      assert result.name == "Acme Corp"  # just testing the mock return

  # ✅ valuable unit test — validates business rule
  def test_create_partner_raises_for_duplicate_cnpj():
      repo = mock_repo(existing=_make_partner(cnpj="12345678000100"))
      with pytest.raises(DuplicateCnpj):
          PartnerService(repo).create(cnpj="12345678000100")
  ```

- **Date-sensitive test without time freezing**: tests that use hardcoded dates that depend on being in the future will become flaky as time advances. Flag any test with a hardcoded date that is compared to `date.today()` without freezing time. The fix is `unittest.mock.patch` targeting the module that calls `date.today()`.

- **Alembic migration missing in PR**: if a model changed columns, constraints, or table structure, there must be a corresponding Alembic migration in the same PR. Missing migrations cause silent schema drift between environments.

## 🔵 Suggestion

- **Portuguese in code identifiers**: Portuguese is acceptable only in UI copy. Code, API fields, and DB column names must always be in English.

- **Missing blank lines between logical contexts inside functions**: distinct concerns within a function body must be separated by a blank line (e.g. validation block → blank line → action/return). Lines belonging to the same concern stay together.

- **`Time(timezone=True)` on a time-of-day column**: `time` columns represent a clock time with no offset — use `Time()` without timezone. Only full timestamp columns use `DateTime(timezone=True)`.

- **Cornice view missing `@view_config` validators**: Cornice views that accept request bodies should declare `validators=(colander_body_validator,)` or the Marshmallow equivalent. Skipping validation lets malformed requests reach the service layer.
