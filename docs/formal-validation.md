# Formal Validation — Lean 4 Proof Backing

The *formal termination guarantee* / "formally validated" language used to
describe `fulcrum-trust` — e.g. in `CLAUDE.md` and the *Part of the Fulcrum
Architecture* table in the [README](../README.md), which lists
[`Fulcrum-Proofs`](https://github.com/Fulcrum-Governance/Fulcrum-Proofs) as the
formal core — is backed by the Lean 4 trust-termination theorems in that
repository. The authoritative proof-to-implementation mapping lives at:

- `Fulcrum-Proofs/proofs/lean/Proofs/TrustTermination.lean` — Lean source
  for the Beta(α, β) termination guarantees.
- `Fulcrum-Proofs/README.md` § "Trust Termination Proofs" — the theorem
  inventory (`trust_monotone_decreasing`, `trust_failure_degrades`,
  `trust_threshold_reachable`, `trust_termination_invariant`,
  `trust_safety_invariant`, `trust_cumulative_degradation`,
  `trust_guaranteed_termination`, …).
- `fulcrum-io/docs/formal-verification/CORRESPONDENCE.md` — narrative
  proof-to-runtime cross-walk (manually maintained; the canonical
  machine-readable closure manifest is
  `Fulcrum-Proofs/claims/claim_closure.yaml`).

Without that cross-reference, public readers cannot verify the
"formally validated" claim.

---

*Provenance: this note was lifted from the former `.planning/PROJECT.md`
(§ "Formal Validation — Lean 4 Proof Backing", which closed contradiction-ledger
F-032) when the superseded GSD planning tree was archived to
[`docs/_archive/2026-06-conductor-migration/`](_archive/2026-06-conductor-migration/)
in June 2026. It is preserved here as a durable, public home so the proof
cross-reference — and the F-032 closure — does not regress.*
