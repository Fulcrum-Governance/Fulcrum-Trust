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

## Bounded detection latency (`alpha_max`) — published anchor

The optional `TrustConfig.alpha_max` cap (added July 2026) is the engine-side
realization of the *hardened model variant* published in D4 §3.7, Theorem 3.9
(`capped_prior_strict_responsiveness`, with helper
`capped_success_update_bounded`, mapped to `KernelVariants.lean` in the
released Zenodo supplement) —
[DOI 10.5281/zenodo.19900714](https://doi.org/10.5281/zenodo.19900714).
The paper frames that theorem as "a hardened model variant, not a claim about
the current implementation"; this knob closes the stated gap on the
implementation side.

Claims scope: the knob is **Implemented**; the bound `q·(α_max+1)` is
**Proved** for the discrete capped Lean model only (Laplace `(α+1)/(α+β+2)`
over `Nat`). The deployed raw `α/(α+β)` float estimator has a different,
tighter minimal constant (`β > α(q−p)/p`). Never present the Lean constant as
the operational detection latency — see the correspondence note in the
[README](../README.md#bounded-detection-latency-alpha_max).

## Two-regime recovery — four-state machine correspondence

The cooldown-gated `HALF_OPEN` recovery probe (added July 2026;
`TrustConfig.recovery_cooldown_seconds`) routes recovery through the
`CLOSED → OPEN → HALF_OPEN → CLOSED` cycle instead of the direct `OPEN → CLOSED`
edge. That deployed four-state machine *corresponds to* the `ValidTransition`
transition relation formalized in
[`Fulcrum-Proofs`](https://github.com/Fulcrum-Governance/Fulcrum-Proofs) at the
`v0.2.0` tag, whose regime-conditioned docstring distinguishes the direct-edge
default from the cooldown-gated probe path.

Claims scope: the recovery machine is **Implemented** and **Tested**; the
mapping to `ValidTransition` is a **narrative cross-walk, not a new proof** — the
cooldown duration is an operational parameter, not a Lean-verified quantity. Cite
the `v0.2.0` tag, not `main`.

---

*Provenance: this note was lifted from the former `.planning/PROJECT.md`
(§ "Formal Validation — Lean 4 Proof Backing", which closed contradiction-ledger
F-032) when the superseded GSD planning tree was archived to
[`docs/_archive/2026-06-conductor-migration/`](_archive/2026-06-conductor-migration/)
in June 2026. It is preserved here as a durable, public home so the proof
cross-reference — and the F-032 closure — does not regress.*
