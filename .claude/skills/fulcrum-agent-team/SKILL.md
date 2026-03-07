---
name: fulcrum-agent-team
description: Build Fulcrum features using Claude Code Agent Teams. Takes a plan document path and optional team size. Spawns specialized agents in tmux split panes with contracts and validation gates.
argument-hint: [plan-path] [num-agents]
user-invocable: true
disable-model-invocation: true
---

# Build with Fulcrum Agent Team

You are coordinating a build using Claude Code Agent Teams for the Fulcrum AOS ecosystem. Read the plan document, determine the right team structure, spawn teammates with contracts, and orchestrate the build.

## Arguments

- **Plan path**: `$ARGUMENTS[0]` - Path to a markdown plan file (e.g., `docs/plans/adr-010-implementation-plan.md`)
- **Team size**: `$ARGUMENTS[1]` - Number of agents (optional — determined automatically if omitted)

## Step 1: Read the Plan and Load Context

Read the plan document at `$ARGUMENTS[0]`. Then MANDATORY — also read these files:
1. `docs/ADR-010-engineering-intel-adoption.md` — implementation decisions
2. `docs/fulcrum-engineering-intel-brief.md` — verified external patterns with source file paths
3. `CLAUDE.md` — project conventions and testing requirements

Understand:
- What are we building?
- What are the major components/layers?
- What are the dependencies between components?
- What is the wave/phase structure?

## Step 2: Determine Team Structure

If team size is specified (`$ARGUMENTS[1]`), use that number of agents.

If NOT specified, analyze the plan and determine the optimal team size based on:
- **Number of independent work streams** (implementation, testing, documentation)
- **Parallelization potential** (what can be built simultaneously?)
- **Sequential dependencies** (what MUST happen in order?)

**Fulcrum-specific guidelines:**
- 2 agents: Simple pattern — one implements, one tests
- 3 agents: Standard — implementer, tester, documenter (recommended for ADR-010 waves)
- 4 agents: Complex — split implementation across two agents when patterns touch separate files

For each agent, define:
1. **Name**: Short, descriptive (e.g., "implementer", "tester", "documenter")
2. **Ownership**: What files/directories they own exclusively
3. **Does NOT touch**: What's off-limits (prevents conflicts)
4. **Key responsibilities**: What they're building

## Step 3: Set Up Agent Team

Enable tmux split panes so each agent is visible:

```
teammateMode: "tmux"
```

Note: cmux users — cmux is the visual terminal app; tmux runs as the programmatic layer inside it. Start a tmux session inside your cmux workspace before launching Claude Code.

## Step 4: Define Contracts

Before spawning agents, define the integration contracts between work streams. This upfront work enables all agents to spawn in parallel without diverging.

### Fulcrum Contract Chain

For ADR-010 implementation patterns, the contract chain is:

```
Types (types.py) → defines data structures → Implementation (manager.py, context.py, flusher.py)
Implementation → defines public API surface → Tests (test_*.py)
Implementation + Tests → defines what exists → Documentation (api-reference.md, README.md, CHANGELOG.md)
```

### Author the Contracts

From the plan, define each integration contract:

**Types → Implementation contract:**
- Exact class signatures (`TrustCircuitOpen(Exception)` with `pair_id`, `trust_score`, `threshold`)
- Exact dataclass field additions (`circuit_state: str = "CLOSED"` on `TrustState`)
- New parameter signatures (`raise_on_break: bool = False`, `async_flush: bool = False`)

**Implementation → Tests contract:**
- What public methods exist and their signatures
- What exceptions can be raised and when
- What concurrent behavior must be tested
- What coverage threshold must be met (95%+)

**Implementation → Docs contract:**
- Every new public class, method, parameter must appear in `docs/api-reference.md`
- Architecture diagram in `README.md` must reflect new modules
- `CHANGELOG.md` must have entries for every change

### Cross-Cutting Concerns

Assign ownership explicitly:
- **Backward compatibility**: Implementer owns — all new parameters default to current behavior
- **Import/export updates**: Implementer owns — `__init__.py` must export new types
- **Type strictness**: Tester validates — `mypy --strict` must pass on all new code
- **Lint cleanliness**: Tester validates — `ruff check .` must pass

### Contract Quality Checklist

Before including a contract in agent prompts, verify:
- Are class signatures exact (parameter names, types, defaults)?
- Are exception conditions documented (when does `TrustCircuitOpen` fire)?
- Are new parameter defaults specified (what happens when omitted)?
- Are file ownership boundaries explicit (who touches `manager.py` in which wave)?
- Are test coverage thresholds stated per module?
- Are concurrent behavior expectations documented (what must `asyncio.gather()` tests prove)?

## Step 5: Spawn All Agents in Parallel

With contracts defined, spawn all agents simultaneously. Enter **Delegate Mode** (Shift+Tab) before spawning. You should NOT implement code yourself — your role is coordination.

### Spawn Prompt Structure

Each agent receives:

```
You are the [ROLE] agent for this Fulcrum build.

## Your Ownership
- You own: [directories/files]
- Do NOT touch: [other agents' files]

## What You're Building
[Relevant section from plan — include the specific wave/task details]

## Contracts

### Contract You Produce
[Include the lead-authored contract this agent is responsible for]
- Build to match this exactly
- If you need to deviate, message the lead and wait for approval

### Contract You Consume
[Include the lead-authored contract this agent depends on]
- Build against this interface exactly — do not guess or deviate

### Cross-Cutting Concerns You Own
[Explicitly list integration behaviors this agent is responsible for]

## Fulcrum-Specific Constraints
- All new parameters must have defaults preserving backward compatibility
- No third-party dependencies beyond Python stdlib
- Type hints on all public APIs (mypy strict)
- Do NOT modify files outside your ownership scope

## Coordination
- Message the lead if you discover something that affects a contract
- Ask before deviating from any agreed contract
- Flag cross-cutting concerns that weren't anticipated
- Share with [other agent] when: [trigger — e.g., "when new public method is added"]
- Challenge [other agent]'s work on: [integration point — e.g., "import paths match"]

## Before Reporting Done
Run these validations and fix any failures:
1. [specific validation command — e.g., pytest, mypy, ruff]
2. [specific validation command]
Do NOT report done until all validations pass.
```

### Default Fulcrum Agent Roles

**Implementer agent** owns:
- `fulcrum_trust/` (all source files)
- Does NOT touch: `tests/`, `docs/`, `README.md`, `CHANGELOG.md`
- Validates: `python -c "from fulcrum_trust import TrustCircuitOpen, TrustManager; print('OK')"`

**Tester agent** owns:
- `tests/` (all test files)
- Does NOT touch: `fulcrum_trust/`, `docs/`
- Validates: `pytest tests/ -v --cov=fulcrum_trust --cov-report=term-missing` (95%+ on new modules)
- Also runs: `mypy fulcrum_trust/ --strict` and `ruff check .`

**Documenter agent** owns:
- `docs/api-reference.md`, `README.md`, `CHANGELOG.md`
- Does NOT touch: `fulcrum_trust/`, `tests/`
- Validates: all new public surface documented, architecture diagram current

## Step 6: Facilitate Collaboration

All agents are working in parallel. Your job as lead is to keep them aligned and unblock them.

### During Implementation
- Relay messages between agents when they flag contract issues
- If an agent needs to deviate from a contract, evaluate the change, update the contract, and notify all affected agents
- Unblock agents waiting on decisions
- Track progress through the shared task list

### Pre-Completion Contract Verification
Before any agent reports "done", run a contract diff:
- "Implementer: what exact public API surface did you create?"
- "Tester: what exact imports and methods are you testing?"
- Compare and flag mismatches before integration

### Cross-Review
Each agent reviews another's work:
- Tester reviews Implementer's code for testability and type correctness
- Documenter reviews Implementer's docstrings for completeness
- Implementer reviews Tester's assertions for correctness

## Collaboration Patterns

**Anti-pattern: Parallel spawn without contracts** (agents diverge)
```
Lead spawns all 3 agents without defining interfaces
Implementer adds raise_on_break but Tester doesn't know about it ❌
```

**Anti-pattern: Fully sequential** (defeats purpose of agent teams)
```
Lead spawns implementer → waits → spawns tester → waits → spawns documenter
Only one agent works at a time ❌
```

**Anti-pattern: "Tell them to talk"** (they won't reliably)
```
Lead tells implementer "share your API surface with tester when done"
Implementer sends contract but tester already wrote half the tests to wrong signatures ❌
```

**Good pattern: Lead-authored contracts, parallel spawn**
```
Lead reads plan → defines all contracts upfront → spawns all agents with contracts
All agents build simultaneously to agreed interfaces ✅
```

**Good pattern: Active collaboration during parallel work**
```
Implementer: "I need to add a metadata dict to TrustCircuitOpen — messaging the lead"
Lead: "Approved. Tester, TrustCircuitOpen now has an optional metadata attribute. Update your assertions."
Tester: "Got it, adding metadata test coverage now" ✅
```

**Good pattern: Wave-gated parallelism**
```
Wave 1: Implementer does types-only changes (0.5 day)
Wave 2: Implementer + Tester + Documenter run in parallel (tests can target known API)
Lead validates between waves ✅
```

## Task Management

Create a shared task list from the plan's wave structure. Block tasks that genuinely require another agent's output:

```
[ ] Wave 1: Implementer — types.py changes (TrustCircuitOpen, circuit_state)
[ ] Wave 2a: Implementer — context.py + manager.py (depends on Wave 1)
[ ] Wave 2a: Tester — test_context.py, test_types.py (can start after Wave 1)
[ ] Wave 2a: Documenter — start api-reference.md updates (can start after Wave 1)
[ ] Wave 2b: Implementer — flusher.py + manager.py (depends on Wave 2a)
[ ] Wave 2b: Tester — test_flusher.py (depends on Wave 2b implementer)
[ ] Wave 3: All — final integration test + doc polish (depends on all Wave 2)
```

## Common Pitfalls to Prevent

1. **File conflicts**: Two agents editing the same file → Assign clear ownership per agent
2. **Lead over-implementing**: You start coding → Stay in Delegate Mode (Shift+Tab)
3. **Isolated work**: Agents don't communicate → Require explicit handoffs via lead relay
4. **Vague boundaries**: "Help with backend" → Specify exact files/responsibilities
5. **Missing dependencies**: Agent B waits on Agent A forever → Track blockers actively
6. **Parallel spawn without contracts**: Agents diverge on interfaces → Define contracts first
7. **Breaking backward compatibility**: New parameter without default → All new params must default to current behavior
8. **Adding dependencies**: Import from third-party → Python stdlib only for fulcrum-trust
9. **Skipping validation**: Agent reports done without running tests → Each agent has a validation checklist

## Step 7: Validation

Validation happens at two levels: **agent-level** (each agent validates their domain) and **lead-level** (you validate the integrated system).

### Agent Validation

**Implementer validates:**
- `python -c "from fulcrum_trust import TrustCircuitOpen, TrustManager; print('OK')"` — imports clean
- All new files have complete docstrings matching existing style
- No breaking changes to existing public API

**Tester validates:**
- `pytest tests/ -v` — all tests pass, zero failures
- `pytest tests/ --cov=fulcrum_trust --cov-report=term-missing` — 95%+ on new modules
- `mypy fulcrum_trust/ --strict` — zero errors on new code
- `ruff check . && ruff format --check .` — lint clean

**Documenter validates:**
- Every new public class, method, parameter appears in `docs/api-reference.md`
- `README.md` architecture diagram includes new modules
- `CHANGELOG.md` has entries for all changes

### Lead Validation (End-to-End)

After ALL agents return, run end-to-end validation yourself:

1. **Full test suite**: `pytest tests/ -v --cov=fulcrum_trust --cov-report=term-missing`
2. **Type check**: `mypy fulcrum_trust/ --strict`
3. **Lint**: `ruff check . && ruff format --check .`
4. **Integration test**: `TrustManager(async_flush=True)` with `FileStore` persists events
5. **Concurrency test**: `asyncio.gather()` evaluations don't cross-contaminate
6. **Backward compat**: Existing tests pass without any modifications
7. **Doc completeness**: All new surface documented

If validation fails:
- Identify which agent's domain contains the issue
- Re-spawn that agent with the specific problem
- Re-run validation after fix

## Definition of Done

The build is complete when:
1. All agents report their work is done
2. Each agent has run their validation checklist
3. Lead has run full end-to-end validation
4. Cross-review feedback has been addressed
5. The plan's wave success gates are all met
6. ADR-010 status can be updated from "Proposed" to "Accepted"

## Fulcrum-Specific Constraints — What NOT to Do

These constraints apply to ALL agents across ALL waves:
- Do NOT break backward compatibility — all new parameters default to current behavior
- Do NOT add third-party dependencies — stdlib only (`queue`, `threading`, `atexit`, `contextvars`)
- Do NOT implement the full Langfuse MediaUploadConsumer pattern — simple queue + thread + flush
- Do NOT use `nest_asyncio.apply()` — fulcrum-trust should be natively async-compatible
- Do NOT add CEL support to the policy engine (deferred per ADR-010)
- Do NOT create `cmd/secure-mcp/` or any fulcrum-io changes (D2 scope, separate plan)
- Do NOT refactor existing store implementations beyond adding `circuit_state` field

---

## Execute

Now read the plan at `$ARGUMENTS[0]` and begin:

1. Read and understand the plan (and load mandatory context files)
2. Determine team size (use `$ARGUMENTS[1]` if provided, otherwise decide)
3. Define agent roles, ownership, and validation requirements
4. Map the contract chain and define all integration contracts from the plan
5. Enter Delegate Mode (Shift+Tab)
6. Spawn all agents in parallel with contracts and validation checklists in their prompts
7. Monitor agents, relay messages, mediate contract deviations
8. Run contract diff before integration — compare implementer's API vs tester's imports
9. When all agents return, run end-to-end validation yourself
10. If validation fails, re-spawn the relevant agent with the specific issue
11. Confirm the build meets the plan's wave success gates
