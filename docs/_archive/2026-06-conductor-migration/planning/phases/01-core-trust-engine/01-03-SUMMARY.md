---
phase: 01-core-trust-engine
plan: "03"
subsystem: infra
tags: [pyproject, hatchling, pytest, pytest-cov, mypy, ruff, github-actions, ci, packaging]

# Dependency graph
requires: []
provides:
  - "pyproject.toml: build system (hatchling), zero-dep package, dev extras (pytest, pytest-cov, mypy, ruff)"
  - "Coverage gate: 95% enforced in both addopts and [tool.coverage.report] (belt-and-suspenders)"
  - "README.md with canonical quick-start: TrustManager, TrustOutcome, evaluate(), get_trust_score(), should_terminate(), FileStore"
  - ".github/workflows/ci.yml: lint + format-check + typecheck + test matrix (Python 3.9/3.11/3.12)"
affects: [01-01, 01-02, all-future-plans]

# Tech tracking
tech-stack:
  added: [hatchling>=1.21, pytest>=7.0, pytest-cov>=4.0, mypy>=1.0, ruff>=0.1]
  patterns:
    - "Belt-and-suspenders coverage: --cov-fail-under=95 in addopts AND fail_under=95 in [tool.coverage.report]"
    - "Adapters excluded from 95% coverage gate (omit = fulcrum_trust/adapters/*) — separate threshold in Phase 2"
    - "CI matrix: 3.9 (compat floor) + 3.11/3.12 (modern) — skip 3.10 to reduce CI time"
    - "fail-fast: false in CI matrix — all versions run even if one fails"

key-files:
  created:
    - pyproject.toml
    - .github/workflows/ci.yml
  modified:
    - README.md

key-decisions:
  - "Coverage gate in both [tool.pytest.ini_options] addopts AND [tool.coverage.report] — required for gate to fire in all invocation modes (RESEARCH.md Pitfall 7)"
  - "adapters/ excluded from 95% coverage gate — Phase 2 will establish separate 90% threshold"
  - "ruff format --check in CI (not --fix) — fails on wrong formatting, does not auto-commit"
  - "mypy --ignore-missing-imports in CI — numpy not installed in CI dev deps; strict errors still surface"
  - "README overwritten from scaffold — Phase 4 polish phase will expand with full API reference"

patterns-established:
  - "Package infra pattern: hatchling build, zero runtime deps, optional numpy, dev extras group"
  - "CI pattern: lint -> format-check -> typecheck -> test (ordered by speed, fail fast on cheap checks)"

requirements-completed: [TRUST-01, TRUST-06]

# Metrics
duration: 2min
completed: 2026-02-18
---

# Phase 01 Plan 03: Package Infrastructure Summary

**pyproject.toml with hatchling build + 95% coverage gate + GitHub Actions CI matrix (Python 3.9/3.11/3.12) + README quick-start for TrustManager**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-18T23:14:08Z
- **Completed:** 2026-02-18T23:15:47Z
- **Tasks:** 2
- **Files modified:** 3 (pyproject.toml created, README.md overwritten, .github/workflows/ci.yml created)

## Accomplishments

- Created complete pyproject.toml with hatchling build system, zero runtime dependencies, dev extras (pytest/pytest-cov/mypy/ruff), and 95% coverage gate enforced in both pytest addopts and [tool.coverage.report]
- Wrote GitHub Actions CI workflow with Python 3.9/3.11/3.12 matrix, fail-fast=false, and ordered steps: lint -> format-check -> typecheck -> test
- Replaced scaffold README with accurate quick-start showing all five public API entry points: TrustManager, TrustOutcome, evaluate(), get_trust_score(), should_terminate(), and FileStore usage

## Task Commits

Each task was committed atomically:

1. **Task 1: pyproject.toml — build, test, lint, type configuration** - `20dec87` (chore)
2. **Task 2: README.md skeleton and GitHub Actions CI workflow** - `2525452` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `/Users/td/ConceptDev/Projects/fulcrum-trust/pyproject.toml` — hatchling build, requires-python >=3.9, zero runtime deps, dev extras, pytest/coverage/mypy/ruff config
- `/Users/td/ConceptDev/Projects/fulcrum-trust/README.md` — overwritten with canonical quick-start (TrustManager API, FileStore, architecture diagram, badges)
- `/Users/td/ConceptDev/Projects/fulcrum-trust/.github/workflows/ci.yml` — CI pipeline: matrix 3.9/3.11/3.12, ruff check, ruff format --check, mypy, pytest -v

## Decisions Made

- Coverage gate placed in BOTH `[tool.pytest.ini_options]` addopts (`--cov-fail-under=95`) AND `[tool.coverage.report]` (`fail_under = 95`) — ensures gate fires whether running pytest directly or via coverage CLI (belt-and-suspenders per RESEARCH.md Pitfall 7)
- `fulcrum_trust/adapters/*` excluded from 95% gate — adapters are Phase 2 with separate 90% threshold
- `ruff format --check` (not `--fix`) in CI — prevents silent auto-commits
- `mypy --ignore-missing-imports` in CI — numpy not in dev extras; strict type errors still surface
- README scaffold overwritten entirely — the existing content used slightly different API signatures; Phase 4 polish will expand

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. CI will activate automatically when code is pushed to the GitHub repository.

## Next Phase Readiness

- `pip install -e ".[dev]"` exits 0, all dev tools (pytest, mypy, ruff) installed and importable
- pyproject.toml is valid TOML with all required sections; coverage gate confirmed in both locations
- CI workflow triggers on push to main and PRs targeting main; matrix covers Python 3.9/3.11/3.12
- README contains accurate quick-start matching the planned public API surface
- Ready for plan 01-01 (core types/evaluator/manager/stores) and 01-02 (test suite)

## Self-Check: PASSED

- pyproject.toml: FOUND
- README.md: FOUND
- .github/workflows/ci.yml: FOUND
- 01-03-SUMMARY.md: FOUND
- Commits 20dec87, 2525452: FOUND

---
*Phase: 01-core-trust-engine*
*Completed: 2026-02-18*
