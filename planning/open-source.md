# Open Source Readiness Plan – pyramid-temporal

## Objective

Prepare pyramid-temporal for public open source release: ensure no secrets or sensitive data are exposed, resolve branding/attribution, and document decisions. No code changes until this plan is approved.

---

## 1. Secrets and credentials audit

### 1.1 Result: no secrets in repository

- **No hardcoded API keys, passwords, or tokens** in source, config, or docs.
- **`.envrc`** is in `.gitignore` – not tracked; safe.
- **README** only shows the *pattern* `context.request.registry.settings.get('notification.api_key')` – no value.
- **GitHub Actions**: release workflow uses OIDC (`role-to-assume`) and repository **variables** (`vars.CODEARTIFACT_DOMAIN`, `vars.AWS_ACCOUNT_ID`, etc.). No secrets committed; credentials stay in GitHub (vars/secrets).
- **CodeArtifact action** (`.github/actions/codeartifact-login/action.yml`) accepts `aws-access-key-id` / `aws-secret-access-key` as optional inputs; the current release workflow does not pass them (it uses OIDC). No leak from the repo.

### 1.2 Acceptable / optional cleanup

- **Docker Compose** (`.dev-local/docker-compose.yml`): `POSTGRES_PASSWORD: temporal` and `POSTGRES_PWD: temporal` – standard dev defaults. Acceptable as-is; optionally add a short comment in the file or in README that these are for local dev only and should be changed in non-local environments.

**Conclusion:** No mandatory secret removal. Optional: document that Docker Compose passwords are for local use only.

---

## 2. Branding and attribution

Current state:

| Location           | Current value / note |
|--------------------|----------------------|
| **LICENSE**        | `Copyright (c) 2025, Robbin dev team` |
| **pyproject.toml** | `authors = ["Robbin dev team <fdev@robbin.com.br>"]` |
| **pyproject.toml** | `repository` / `documentation` → `cartaorobbin/pyramid-temporal` (GitHub) |
| **mkdocs.yml**     | `site_author: Robbin dev team`, `copyright: Maintained by Tomas Correa` (github.com/cartaorobbin) |
| **README / CONTRIBUTING / docs** | Point to `cartaorobbin/pyramid-temporal` |

**Decisions needed (no code until you decide):**

1. **Copyright and LICENSE**  
   Keep “Robbin dev team” as copyright holder, or change to you / “Tomas Correa” / another entity?

2. **Authors in pyproject.toml**  
   Keep “Robbin dev team <fdev@robbin.com.br>”, or list yourself (e.g. “Tomas Correa <…>”) or both?

3. **Docs (mkdocs)**  
   Keep “Robbin dev team” and “Maintained by Tomas Correa” or align with the chosen copyright/authors?

4. **GitHub repo URL**  
   Repository and docs already point to `cartaorobbin/pyramid-temporal`. Is that the final public URL (e.g. under your account or an org)?

---

## 3. CI/CD and release

- **on-release-main.yml** (push/PR): quality, tox, codecov, docs build – fine for public; no secrets.
- **on-release-codeartifact.yml** (on release published): builds, publishes to **AWS CodeArtifact**, then deploys docs with `mkdocs gh-deploy`.

For a public repo:

- The **CodeArtifact** workflow will only succeed where the repo has the required GitHub variables set (e.g. `AWS_ACCOUNT_ID`, `CODEARTIFACT_DOMAIN`, `CODEARTIFACT_OWNER`, `CODEARTIFACT_REPOSITORY_NAME`). In a fork or a repo without those vars, that job will fail; the rest of the workflow (e.g. docs) might still run if not gated on it.
- **Decision:** **Option B – PyPI only.** Implemented: release workflow now publishes only to PyPI (CodeArtifact workflow removed). Uses organization secret `PYPI_TOKEN` for the release job.

---

## 4. Other checks

- **.devcontainer/docker-compose.yml** – network name `internal` is just a Docker network name; no company-internal meaning.
- **codecov.yaml** – config only; no secrets.
- **planning/** and **.cursor/rules/** – no secrets; planning has some code snippets (style preference only; not a blocker for open source).
- **Dependencies** – all from public PyPI; no private or internal package sources in the committed config.

---

## 5. Optional improvements (after approval)

- Add a **SECURITY.md** (e.g. “how to report vulnerabilities”) if you want a clear process for the public.
- Add a short **“Publishing”** or **“Release”** section in README or CONTRIBUTING describing how releases work (CodeArtifact vs PyPI, who has vars, etc.).
- If you change copyright/authors, do a single pass over LICENSE, pyproject.toml, and mkdocs.yml for consistency.

---

## 6. Summary and next steps

- **Secrets:** None found; repo is safe to open source from a secrets perspective. Optional: document Docker Compose passwords as dev-only.
- **Blockers:** None technical. Pending: your choices on **copyright**, **authors**, **docs attribution**, and **release strategy** (CodeArtifact-only vs add PyPI).

Next step: you confirm or adjust the decisions in sections 2 and 3 (and any optional items in 5). After that, we can apply the agreed changes (no code before planning approval).
