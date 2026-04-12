# Taskmanagement-App — Backend

Python / FastAPI / Poetry / SQLAlchemy / Alembic / mypy / pytest

## Quick Commands

```bash
poetry run uvicorn taskmanagement_app.main:app --reload   # dev server (port 8000)
poetry run alembic upgrade head                           # apply migrations
poetry run pytest --cov                                   # run tests
poetry run black . && poetry run isort . && poetry run flake8 && poetry run mypy .  # quality checks
```

## Quality Gates (all must pass before a PR)

| Tool | Purpose |
|---|---|
| `black` | formatting (line length 88) |
| `isort` | import order (black profile) |
| `flake8` | lint (max-line-length 88) |
| `mypy` | type checking |
| `pytest` | tests with coverage |

## Deployment Rule

**Always bump `pyproject.toml` version when backend changes should reach production.** The deploy pipeline only fires when the version changes. Use semver: `patch` / `minor` / `major`.

## Adding a Feature (checklist)

1. Create or update SQLAlchemy model in `db/models/`
2. Generate + apply Alembic migration: `poetry run alembic revision --autogenerate -m "description"` then `upgrade head`
3. Create/update Pydantic schemas in `schemas/`
4. Implement CRUD in `crud/`
5. Wire endpoint in `api/v1/endpoints/`
6. Write tests in `tests/`
7. Run all quality checks

## E2E Tests

End-to-end tests live in `tests/e2e/` and run against a **live server** (not TestClient).

```bash
# Start the server first
poetry run uvicorn taskmanagement_app.main:app --reload &

# Smoke tests only (read-only, safe for production)
poetry run pytest tests/e2e/ -m smoke -v

# Full suite (includes write operations — local/CI only)
poetry run pytest tests/e2e/ -v
```

**Two modes:**
- `@pytest.mark.smoke` — read-only tests that verify API health. Run post-deployment against production.
- Full suite — includes CRUD lifecycle, user management, data export/import. Creates and cleans up test data.

**Credentials:** The conftest auto-loads `.env` for admin credentials and bootstraps a temporary test user via the admin API. Override with env vars: `E2E_BASE_URL`, `E2E_USERNAME`, `E2E_PASSWORD`, `E2E_ADMIN_USERNAME`, `E2E_ADMIN_PASSWORD`.

**CI integration:** The `e2e-tests` job in `ci.yml` runs the full suite on PRs. The `smoke-test` job in `deploy.yml` runs smoke tests after deployment (requires `DEPLOY_URL`, `E2E_USERNAME`, `E2E_PASSWORD` secrets).

## API Docs (when server is running)

- Swagger: http://localhost:8000/docs
- OpenAPI JSON: http://localhost:8000/openapi.json

## Further Reading

- Code style, patterns, and conventions: [.github/copilot-instructions.md](.github/copilot-instructions.md)
- Production deployment (systemd + GitHub Actions): [README_DEPLOYMENT.md](README_DEPLOYMENT.md)
- PR workflow and version bump rules: [../docs/pr-workflow.md](../docs/pr-workflow.md)

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **Taskmanagement-App** (896 symbols, 3075 relationships, 73 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/Taskmanagement-App/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/Taskmanagement-App/context` | Codebase overview, check index freshness |
| `gitnexus://repo/Taskmanagement-App/clusters` | All functional areas |
| `gitnexus://repo/Taskmanagement-App/processes` | All execution flows |
| `gitnexus://repo/Taskmanagement-App/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
