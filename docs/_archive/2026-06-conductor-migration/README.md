# Archive — 2026-06 Conductor migration

Superseded planning artifacts from the original **GSD** ("get-shit-done")
sprint workflow, moved here when `fulcrum-trust` migrated to Conductor
lane-based work. The dead GSD *tooling* was removed earlier (commit `e6dd5f6`);
this archive holds the leftover planning *content*.

Retained for historical provenance only — **nothing in this folder is a live
contract.** For current project state see `fulcrum_trust/__init__.py`
(`__version__`), `CHANGELOG.md`, `README.md`, and the live ADRs under `docs/`.

## Contents

- `planning/` — the former top-level `.planning/` tree: `PROJECT.md`,
  `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, `config.json`, and
  `phases/01..04/` (a `PLAN` / `SUMMARY` / `RESEARCH` / `VERIFICATION` record
  per phase). These document the Feb–May 2026 v0.1.0 sprint; the package has
  since shipped v0.1.0 → v0.2.0. Requirement checkboxes and the
  "ship March 17, 2026" dates are historical.
- `adr-010-implementation-plan.md` — the former
  `docs/plans/adr-010-implementation-plan.md`: the sprint *execution* plan for
  ADR-010 (targeted "before March 17, 2026"; its D1 patterns are now
  implemented). The ADR *decision record* it implements remains **live** at
  `docs/ADR-010-engineering-intel-adoption.md`.

## Content lifted out before archiving (still live)

- The **"Formal Validation — Lean 4 Proof Backing"** subsection of
  `planning/PROJECT.md` — the Lean proof cross-reference
  (`TrustTermination.lean`, the theorem inventory, `CORRESPONDENCE.md`,
  `claim_closure.yaml`) that substantiates the "formally validated" claim and
  closed contradiction-ledger **F-032** — was lifted to a durable public home
  at [`docs/formal-validation.md`](../../formal-validation.md). It was the only
  load-bearing, repo-local-only content in the tree; everything else here is
  self-describing history that travels intact.

Closed contradiction-ledger items recorded in these files (**F-032** in
`planning/PROJECT.md`, **F-037** in `planning/STATE.md`) remain closed in the
canonical cross-repo claims ledger; the F-032 cross-reference content lives on
at `docs/formal-validation.md`.
