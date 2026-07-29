# Decisions — where they live

**Cross-repo architecture and strategy decisions for the Fulcrum four-repo
system live in one canonical series: fulcrum-io
[`.claude/decisions/`](https://github.com/Fulcrum-Governance/Fulcrum-IO/tree/main/.claude/decisions)
— see its `INDEX.md` for the full numbered table (ADR-001…).** This repo does
not host its own decision series.

## Freeze rule (FUL-353, program parent FUL-266)

- Do **not** create new ADR files in this repo. New decision records — including
  decisions that primarily concern fulcrum-trust — land in the fulcrum-io
  canonical series and reference this repo from there.
- The one historical local record, `docs/ADR-010-engineering-intel-adoption.md`,
  is **frozen as-is**: its content was adopted into the canonical series as
  fulcrum-io `ADR-007` (engineering/intelligence-adoption). Its final
  disposition (annotate vs archive-in-repo) is ledger-gated (Gate A, FUL-349);
  until then it stays untouched. Nothing here is ever deleted — archive-only is
  a program hard rule.

## Why

The 2026-05-17 consolidation established a single numbered series so that
"why did you decide X" has exactly one answer path. Per-repo ADR dirs drifted,
renumbered, and contradicted each other; the canonical series plus this freeze
note is the repair. Numbering authority is the fulcrum-io filesystem
(`ls .claude/decisions/ADR-*.md | sort | tail -1`) — never quoted from prose.
