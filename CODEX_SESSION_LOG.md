# CODEX Session Log

## 2026-05-03 — YC Critical Fixes Trust Pass

What changed
- Replaced the short Apache header in `LICENSE` with the full canonical Apache License 2.0 text from apache.org.
- Added `SECURITY.md` covering trusted-code-only scope, RLM pure-Python sandbox limitations, OS-level isolation guidance for untrusted workloads, least-privilege integration guidance, and a 90-day coordinated disclosure policy via `security@fulcrumlayer.io`.
- Added `no_site_packages = true` to the local mypy config so strict typecheck stays scoped to the project package instead of failing on an unrelated installed `mcp` dependency in the shared developer environment.

What to verify
- `ruff check .`
- `ruff format --check .`
- `mypy fulcrum_trust/ --ignore-missing-imports`
- `pytest -q`

Verification results
- `ruff check .` — passed
- `ruff format --check .` — passed (`43 files already formatted`)
- `mypy fulcrum_trust/ --ignore-missing-imports` — passed after scoping mypy away from unrelated site-packages
- `pytest -q` — passed (`186 passed`)

Notes
- The security policy is aligned with the current prototype runtime, which uses restricted Python execution and is not a security boundary.
- Keep license and security-policy commits separate per the YC execution plan.

Next session
- If all gates are green, push the branch and open the trust-repo PR back to `main`.
- Resume `fulcrum-io` Phase 4 and Phase 5 only after the trust repo is green.
