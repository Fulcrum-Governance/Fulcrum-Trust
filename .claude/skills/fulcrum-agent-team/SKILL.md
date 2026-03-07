---
name: fulcrum-agent-team
description: Orchestrate agent teams to implement Fulcrum engineering patterns from ADR-010. Spawns specialized teammates for implementation, testing, and documentation.
user-invocable: true
disable-model-invocation: false
---

# Fulcrum Agent Team — ADR-010 Implementation

## When to Use This Skill
Use this skill when implementing patterns from the Engineering Intelligence Audit (ADR-010). It spawns a coordinated agent team with specialized roles for code, tests, and docs.

## Prerequisites
- You must be inside a tmux session (cmux runs tmux underneath for split-pane mode)
- Agent teams must be enabled: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- You must be in the fulcrum-trust or fulcrum-io repo directory

## Context Loading — MANDATORY
Before spawning any teammates, the lead agent MUST read:
1. `docs/ADR-010-engineering-intel-adoption.md` — the implementation decisions and step-by-step context
2. `docs/fulcrum-engineering-intel-brief.md` — verified external patterns with source file paths
3. `CLAUDE.md` — project conventions and testing requirements

## Agent Team Structure

Spawn 3 teammates:

### Teammate 1: Implementer
**Role:** Write production code for the assigned pattern
**Working scope:** `fulcrum_trust/` (for D1 patterns) or `internal/` and `cmd/` (for D2 patterns)
**Instructions:**
- Read the specific pattern section from ADR-010 before writing any code
- Follow the implementation order specified in the Claude Code Context Document section
- All new parameters must have defaults that preserve backward compatibility
- Do NOT add dependencies beyond Python stdlib for D1 patterns
- Use strict type hints on all public APIs

### Teammate 2: Tester
**Role:** Write tests achieving 95%+ coverage on all new modules
**Working scope:** `tests/`
**Instructions:**
- Write tests BEFORE reviewing the implementation (red-green pattern)
- Test files mirror the source structure: `tests/test_flusher.py`, `tests/test_context.py`, etc.
- Include concurrency tests: `asyncio.gather()` calls evaluating different pairs must not interfere
- Include shutdown tests: verify graceful flush on process exit
- Run `pytest --cov=fulcrum_trust --cov-report=term-missing` and verify 95%+ on new modules
- Run `mypy fulcrum_trust/ --strict` and verify zero errors on new code
- Run `ruff check .` and verify clean

### Teammate 3: Documenter
**Role:** Update all documentation for new features
**Working scope:** `docs/`, `README.md`, `CHANGELOG.md`
**Instructions:**
- Update `docs/api-reference.md` with new classes, methods, parameters
- Update `README.md` architecture diagram to reflect new modules
- Add CHANGELOG.md entries under next version for each pattern
- Ensure docstrings on all new public classes/methods match existing style

## Implementation Order (from ADR-010)

### D1 Patterns (fulcrum-trust)
Execute in this exact order — dependencies require it:

1. **P-02: TrustCircuitOpen exception** → `fulcrum_trust/types.py`
2. **P-03: ContextVar isolation** → new `fulcrum_trust/context.py` + modify `manager.py`
3. **P-01: Background flusher** → new `fulcrum_trust/flusher.py` + modify `manager.py`
4. **Tests for all three patterns**
5. **Documentation updates**

### D2 Patterns (fulcrum-trust + fulcrum-io)
6. **P-06: Durable quarantine** → modify `types.py`, `manager.py`, all stores
7. **P-08: Well-known discovery endpoint** → new endpoint in `cmd/secure-mcp/`
8. **P-05: Governance metadata headers** → MCP proxy handler

## Verification Gate — MANDATORY
After all teammates complete, the lead MUST:
1. Run `pytest --cov=fulcrum_trust --cov-report=term-missing`
2. Verify 95%+ coverage on ALL new modules (flusher.py, context.py, updated types.py, updated manager.py)
3. Run `mypy fulcrum_trust/ --strict`
4. Run `ruff check . && ruff format --check .`
5. Verify no breaking changes: existing tests still pass without modification
6. Only then declare the task complete

## What NOT to Do
- Do NOT refactor existing store implementations beyond adding `circuit_state` field
- Do NOT add CEL support to the policy engine (deferred per ADR-010)
- Do NOT change the existing TrustManager API in any breaking way
- Do NOT implement the full Langfuse MediaUploadConsumer pattern
- Do NOT use `nest_asyncio.apply()` — fulcrum-trust should be natively async-compatible
