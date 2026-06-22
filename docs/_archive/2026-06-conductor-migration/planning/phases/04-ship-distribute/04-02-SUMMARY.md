---
phase: 04-ship-distribute
plan: "02"
subsystem: infra
tags: [github-actions, pypi, oidc, trusted-publishing, ci-cd, packaging]

# Dependency graph
requires:
  - phase: 04-ship-distribute/04-01
    provides: pyproject.toml with hatchling build backend and package metadata
provides:
  - .github/workflows/publish.yml — automated PyPI publish pipeline via OIDC Trusted Publishing
affects: [04-03, 04-04, pypi-release]

# Tech tracking
tech-stack:
  added: [pypa/gh-action-pypi-publish@release/v1, actions/upload-artifact@v4, actions/download-artifact@v4]
  patterns: [OIDC Trusted Publishing (no stored secrets), TestPyPI-first serialization, job-level minimum privilege]

key-files:
  created: [.github/workflows/publish.yml]
  modified: []

key-decisions:
  - "id-token: write at job level (not workflow level) — minimum privilege per PyPA guide"
  - "TestPyPI → PyPI serialization via needs: publish-testpypi — prevents publishing broken package to real index"
  - "OIDC Trusted Publishing eliminates stored API tokens — short-lived per-job GitHub OIDC tokens"
  - "pypa/gh-action-pypi-publish@release/v1 (not @master — that branch is sunset)"
  - "actions/upload-artifact@v4 and download-artifact@v4 — v3 is deprecated"

patterns-established:
  - "Publish workflow: separate from CI — triggers on v* tag push, never on branch push"
  - "Three-job pattern: build (artifact) → testpypi (validate) → pypi (ship)"

requirements-completed: [DIST-01]

# Metrics
duration: 1min
completed: 2026-02-19
---

# Phase 4 Plan 02: Publish Workflow Summary

**GitHub Actions OIDC Trusted Publishing pipeline: three-job build → TestPyPI → PyPI chain triggered on v* tags, zero stored secrets**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-19T08:17:46Z
- **Completed:** 2026-02-19T08:18:46Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Created `.github/workflows/publish.yml` with three-job pipeline (build, publish-testpypi, publish-pypi)
- OIDC Trusted Publishing configured at job level with `id-token: write` — no stored API tokens or secrets
- TestPyPI-first serialization (`needs: publish-testpypi`) prevents shipping a broken package to the real index
- `twine check dist/*` validates package metadata before upload

## Task Commits

Each task was committed atomically:

1. **Task 1: Create .github/workflows/publish.yml** - `813e393` (feat)

**Plan metadata:** see final commit below

## Files Created/Modified

- `.github/workflows/publish.yml` — Automated PyPI publish pipeline: triggers on v* tags, build job produces sdist+wheel artifact, publish-testpypi uploads to TestPyPI via OIDC, publish-pypi uploads to real PyPI after TestPyPI succeeds

## Decisions Made

- `id-token: write` placed at job level (not workflow level) — minimum privilege, each job only gets OIDC token when it actually needs it
- `pypa/gh-action-pypi-publish@release/v1` (not `@master`) — `@master` branch is sunset per PyPA docs
- `actions/upload-artifact@v4` / `actions/download-artifact@v4` — v3 is deprecated since November 2024
- No `username`, `password`, or `token` fields — OIDC handles authentication via short-lived tokens that expire per-job
- Environment names (`testpypi`, `pypi`) match what gets configured in PyPI Trusted Publishing dashboard

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

Before the workflow can run, two configurations are required in external services:

1. **TestPyPI Trusted Publisher** — at https://test.pypi.org/manage/account/publishing/ add:
   - Publisher: GitHub Actions
   - Repository: `Fulcrum-Governance/fulcrum-trust`
   - Workflow filename: `publish.yml`
   - Environment name: `testpypi`

2. **PyPI Trusted Publisher** — at https://pypi.org/manage/account/publishing/ add:
   - Publisher: GitHub Actions
   - Repository: `Fulcrum-Governance/fulcrum-trust`
   - Workflow filename: `publish.yml`
   - Environment name: `pypi`

3. **GitHub Environments** — create `testpypi` and `pypi` environments in the repo settings (Settings > Environments). No secrets needed — OIDC is token-free.

Once configured, pushing a `v*` tag (e.g. `git tag v0.1.0 && git push origin v0.1.0`) fires the full pipeline.

## Next Phase Readiness

- Publish workflow is in place and ready to fire on `git tag v0.1.0 && git push origin v0.1.0`
- PyPI Trusted Publisher dashboard configuration is the only remaining external setup (plan 04-03 or 04-04 covers this)
- No blockers

## Self-Check: PASSED

- FOUND: `.github/workflows/publish.yml`
- FOUND: `.planning/phases/04-ship-distribute/04-02-SUMMARY.md`
- FOUND: commit `813e393` (feat(04-02): add PyPI publish workflow with OIDC Trusted Publishing)

---
*Phase: 04-ship-distribute*
*Completed: 2026-02-19*
