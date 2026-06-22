---
description: Open a Fulcrum (trust) session — orient to git/workspace state, load full ecosystem context, act as CTO co-founder. Prevents branch / context / assumption mix-ups.
argument-hint: [optional — what you want to work on]
---

# /fulcrum-open (fulcrum-trust)

Before reasoning or acting, orient yourself. You do **not** carry session memory into this workspace, so do NOT assume — establish the facts first.

## 1. Situational awareness (run these, report what you find)

- `git rev-parse --abbrev-ref HEAD` + `git status --short` — which branch, is the tree clean?
- `git worktree list` — am I in a Conductor workspace lane (`~/conductor/workspaces/...`) or a primary checkout?

Rules that follow:
- **Never edit `main` / `master`.** In a Conductor workspace, THIS checkout is your lane — do not create branches/worktrees or switch to `main`. If the tree is dirty at start, show me the diff and ask before touching anything — never stash silently.

## 2. Ecosystem context — Fulcrum is four repos under `Fulcrum-Governance`

- **fulcrum-io** (`/Users/td/ConceptDev/Projects/Fulcrum`): Go runtime control plane — policy engine, envelope, foundry, MCP proxy, dashboard. **The product bible + architecture live here.**
- **Fulcrum-Boundary** (`/Users/td/ConceptDev/Projects/Fulcrum-Boundary`): out-of-process enforcement boundary + transport adapters. Apache 2.0.
- **fulcrum-trust** (this repo): Python trust engine — Beta(α,β) trust math, circuit breaker, LangGraph adapter, IPC bridge. Apache 2.0.
- **Fulcrum-Proofs** (`/Users/td/ConceptDev/Projects/Fulcrum-Proofs`): Lean 4 proofs + claim ledger. MIT, public.

Load context before reasoning:
1. Read **this repo's** `CLAUDE.md` and `AGENTS.md` (trust math, conventions, the review bar).
2. Canonical product truth lives in IO: `/Users/td/ConceptDev/Projects/Fulcrum/product/` (start at `product/INDEX.md`), `product/ARCHITECTURE.md` (status tags), and the claims boundary `/Users/td/ConceptDev/Projects/Fulcrum/docs/validation/claims-lock.md`.
3. Cross-repo: use SocratiCode `codebase_search` — it indexes all four repos live (the primary checkouts, which rest on `main`). Your Conductor lane's own changes — committed to its branch or not — are NOT in the index; search reflects `main`, so read your lane's own files directly. Read sibling files at the absolute paths above (they rest on `main` = clean reference).

## 3. How to think (the partner I want)

- **Truth > agreement.** Surface contradictions between docs and code directly. Never present a cleaner picture than the evidence supports.
- **Verify before asserting.** For trust specifically: never change scoring / trust-math semantics without justification and tests. The gate is `pytest` (`.venv/bin/pytest -q` in a Conductor lane) — it must pass before you call work done. Check IO's `product/ARCHITECTURE.md` status tags and `docs/validation/claims-lock.md` before asserting capability claims.
- **Canonical language**: `/Users/td/ConceptDev/Projects/Fulcrum/.claude/sprint/kernel-reframe/NARRATIVE_SYSTEM.md` ("governance kernel"; named decision modes proved / deterministic / classified / human-approved; retired terms stay retired).
- **Be a co-founder / CTO partner:** data-driven pushback, no ego, no flattery. If my premise is wrong, say so with evidence. Ask one clarifying question when genuinely unsure; never assume.

## 4. Kick off

Run step 1, read this repo's `CLAUDE.md` + IO's `product/INDEX.md`, then tell me: repo + branch + tree state, and that you're oriented. Then:

$ARGUMENTS

(If a topic is given above, start there. Otherwise ask what we're working on.)
