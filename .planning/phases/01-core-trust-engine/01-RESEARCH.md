# Phase 1: Core Trust Engine - Research

**Researched:** 2026-02-18
**Domain:** Python pure-math trust scoring, Beta distribution, exponential decay, Python packaging
**Confidence:** HIGH (core math verified by execution; packaging from official docs)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TRUST-01 | Developer can instantiate TrustEvaluator with configurable Beta(α,β) priors | Beta distribution formula verified; `TrustConfig` dataclass pattern with `alpha_prior`/`beta_prior` fields confirmed working |
| TRUST-02 | TrustManager updates trust scores via Bayesian update from interaction outcomes (success/failure/partial) | Bayesian update formula verified: alpha += 1 (success), beta += 1 (failure), configurable weight for partial; round-trip tested |
| TRUST-03 | TrustManager triggers circuit break when trust score drops below configurable threshold (default 0.3) | Circuit break logic verified: with alpha=1.0, beta=1.0 prior, 2 pure failures trigger break; configurable via threshold param |
| TRUST-04 | Trust scores decay exponentially over time — recent interactions weighted higher than stale ones | Exponential decay formula verified: decay_factor = 0.5^(elapsed/half_life); alpha/beta both decay toward prior (1.0) |
| TRUST-05 | TrustManager persists agent-pair relationship history across evaluations | In-memory dict store pattern verified; order-independent pair_id via sorted SHA256 confirmed working |
| TRUST-06 | Developer can choose in-memory store or JSON file-backed store | JSON file round-trip (dataclass → asdict → json.dumps → json.loads → from_dict) verified working |
</phase_requirements>

---

## Summary

Phase 1 builds the pure Python trust engine with no external dependencies. The mathematics are simple: Beta distribution tracking with alpha (successes) and beta (failures) parameters, trust score computed as `alpha / (alpha + beta)`, starting at 0.5 with an uninformative prior of `(1.0, 1.0)`. All required math uses only Python's built-in `math` module — no scipy, no numpy, no external deps for core logic.

The architecture maps cleanly to four files: `types.py` (enums + dataclasses), `evaluator.py` (TrustEvaluator + trust computation), `manager.py` (TrustManager orchestrating store + evaluator + decay), `decay.py` (exponential decay), and `stores/` (MemoryStore + FileStore). This mirrors the CLAUDE.md architecture exactly. The `Protocol`-based store interface (not ABC) is the right choice for this project because it enables structural subtyping — any dict-like store can satisfy it without inheriting from a base class.

The Python version in `.python-version` is 3.11.13, but CLAUDE.md specifies Python 3.9+. The pyproject.toml should declare `requires-python = ">=3.9"` and code should use `from __future__ import annotations` to enable modern type hint syntax on 3.9. All verified code patterns work on the installed 3.11.13 and are backport-safe to 3.9.

**Primary recommendation:** Build in execution order: types → evaluator (pure math) → stores → decay → manager → tests → package scaffolding. Do not interleave file creation and testing; build all implementation files first, then write tests that give 95%+ coverage.

---

## Standard Stack

### Core (zero external runtime deps)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `math` | 3.9+ built-in | lgamma, exp, log for decay math | No dep needed; math.lgamma sufficient for Beta math |
| Python stdlib `hashlib` | 3.9+ built-in | SHA256 pair_id generation | Order-independent key, deterministic |
| Python stdlib `json` | 3.9+ built-in | File store serialization | Round-trip verified with float/str fields |
| Python stdlib `time` | 3.9+ built-in | Timestamps for decay | time.time() returns float seconds |
| Python stdlib `dataclasses` | 3.9+ built-in | TrustState, TrustConfig | asdict() enables JSON round-trip |
| Python stdlib `enum` | 3.9+ built-in | TrustOutcome | Enum with string values |
| Python stdlib `typing` | 3.9+ built-in | Protocol, TYPE_CHECKING | Store interface without ABC |

### Dev Dependencies
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=7.0 | Test runner | All tests |
| pytest-cov | >=4.0 | Coverage measurement + enforcement | CI gate at 95% |
| mypy | >=1.0 | Strict type checking | `mypy src/` or `mypy fulcrum_trust/` |
| ruff | >=0.1 | Lint + format | Replaces flake8 + isort + black |
| hatchling | >=1.21 | Build backend | Declared in `[build-system]` |

### Optional Runtime Dependency
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| numpy | >=1.21 | Vectorized decay math (optional fast path) | Only if user installs `fulcrum-trust[numpy]` |

**Installation (dev):**
```bash
pip install -e ".[dev]"
```

**Installation (user):**
```bash
pip install fulcrum-trust
# or with numpy fast path:
pip install "fulcrum-trust[numpy]"
```

---

## Architecture Patterns

### Recommended Project Structure

Per CLAUDE.md architecture (flat layout — no `src/` prefix):
```
fulcrum_trust/
├── __init__.py          # Public API: TrustManager, TrustOutcome, TrustState, TrustConfig
├── types.py             # TrustOutcome enum, TrustState dataclass, TrustConfig dataclass, CircuitBreakerState
├── evaluator.py         # TrustEvaluator — Beta(α,β) trust scoring, pure math
├── manager.py           # TrustManager — orchestrates evaluator + store + decay
├── decay.py             # Exponential decay functions
└── stores/
    ├── __init__.py      # Re-exports MemoryStore, FileStore
    ├── base.py          # TrustStore Protocol definition
    ├── memory.py        # In-memory dict store
    └── file.py          # JSON file-backed store
tests/
├── test_types.py        # TrustOutcome, TrustState, TrustConfig validation
├── test_evaluator.py    # Beta computation, updates, edge cases
├── test_manager.py      # evaluate(), should_terminate(), get_trust_score()
├── test_decay.py        # Decay factor math, alpha/beta convergence
└── test_stores.py       # MemoryStore CRUD, FileStore round-trip
```

**Note on src layout vs flat:** Official packaging guide recommends src layout for distributable libraries (prevents import confusion during development). However, CLAUDE.md uses flat layout and the project is already scaffolded this way — stay flat unless a specific problem arises.

### Pattern 1: Beta Distribution Trust Score

**What:** Track `alpha` and `beta` as floats in `TrustState`. Start both at `1.0` (uninformative prior). Trust score = `alpha / (alpha + beta)`.

**When to use:** Every time trust is read or updated.

**Verified formula (from math derivation + execution):**
```python
# Source: verified in Python 3.11.13, consistent with research.md formulas
from __future__ import annotations

@dataclass
class TrustState:
    pair_id: str
    agent_a: str
    agent_b: str
    alpha: float = 1.0      # successes (prior=1 → starts at uncertainty)
    beta: float = 1.0       # failures (prior=1 → starts at uncertainty)
    last_updated: float = field(default_factory=time.time)
    interaction_count: int = 0

    @property
    def trust_score(self) -> float:
        """Compute Beta distribution mean: α / (α + β)."""
        return self.alpha / (self.alpha + self.beta)
```

Initial state: `TrustState(alpha=1.0, beta=1.0)` → `trust_score = 0.5` (satisfies success criterion #3).

### Pattern 2: Bayesian Trust Update

**What:** Add to alpha or beta based on outcome type. This IS the Bayesian update for a Beta-Binomial model.

**Verified behavior:**
```python
# Source: verified by execution
def _apply_outcome(
    state: TrustState,
    outcome: TrustOutcome,
    config: TrustConfig,
) -> TrustState:
    if outcome == TrustOutcome.SUCCESS:
        state.alpha += config.success_weight      # default: 1.0
    elif outcome == TrustOutcome.FAILURE:
        state.beta += config.failure_weight       # default: 1.0
    elif outcome == TrustOutcome.PARTIAL:
        state.alpha += config.partial_alpha_weight  # default: 0.5
        state.beta += config.partial_beta_weight    # default: 0.5
    state.interaction_count += 1
    state.last_updated = time.time()
    return state
```

Pure failures → circuit break in 2 interactions (alpha=1, beta=3, trust=0.25 < 0.3). This is correct — fast termination on consistent failure is the design intent.

### Pattern 3: Order-Independent Pair ID

**What:** Agent pair (`a`, `b`) must produce the same key as (`b`, `a`).

**Verified implementation:**
```python
import hashlib

def pair_id(agent_a: str, agent_b: str) -> str:
    """Generate deterministic order-independent pair key."""
    key = ":".join(sorted([agent_a, agent_b]))
    return hashlib.sha256(key.encode()).hexdigest()[:16]
```

Verified: `pair_id('a','b') == pair_id('b','a')` is True.

### Pattern 4: Exponential Decay

**What:** Decay alpha and beta back toward the prior (1.0) based on elapsed time. Models "stale relationships revert to uncertainty."

**Verified formula:**
```python
# Source: verified by execution — matches half-life decay formula
import math

def apply_decay(
    state: TrustState,
    half_life_seconds: float,
) -> TrustState:
    """Decay alpha/beta toward prior (1.0) using exponential decay."""
    elapsed = time.time() - state.last_updated
    if elapsed <= 0 or math.isinf(half_life_seconds):
        return state
    decay_factor = 0.5 ** (elapsed / half_life_seconds)
    # Decay toward prior of 1.0, not toward 0
    state.alpha = 1.0 + (state.alpha - 1.0) * decay_factor
    state.beta = 1.0 + (state.beta - 1.0) * decay_factor
    return state
```

After 1 half-life: both alpha and beta move halfway from current value toward 1.0.
After many half-lives: both converge to 1.0 → trust_score → 0.5 (satisfies success criterion #5).

**Decay application trigger:** Apply decay lazily — compute and apply when a state is READ from the store, not on a background timer. This avoids threading complexity.

### Pattern 5: Protocol-Based Store Interface

**What:** Use `typing.Protocol` for the store interface, not `ABC`. Enables structural subtyping — any conforming class works without explicit inheritance.

**Verified pattern (Python 3.9+):**
```python
# Source: typing.python.org/en/latest/spec/protocol.html, verified by execution
from __future__ import annotations
from typing import Protocol, runtime_checkable

@runtime_checkable
class TrustStore(Protocol):
    """Interface for trust state persistence."""

    def get(self, pair_id: str) -> TrustState | None: ...
    def put(self, pair_id: str, state: TrustState) -> None: ...
    def delete(self, pair_id: str) -> None: ...
    def all_pairs(self) -> list[str]: ...
```

**Why Protocol over ABC:**
- No forced inheritance — Redis store (future) can implement the protocol without inheriting from a base class
- Structural subtyping means `isinstance(store, TrustStore)` works at runtime with `@runtime_checkable`
- Cleaner than ABC for a store interface with no shared implementation logic

### Pattern 6: MemoryStore Implementation

```python
# Source: verified pattern, dict-based, thread-unsafe (acceptable for v0.1.0)
from __future__ import annotations

class MemoryStore:
    """In-memory trust state store. Not thread-safe."""

    def __init__(self) -> None:
        self._data: dict[str, TrustState] = {}

    def get(self, pair_id: str) -> TrustState | None:
        return self._data.get(pair_id)

    def put(self, pair_id: str, state: TrustState) -> None:
        self._data[pair_id] = state

    def delete(self, pair_id: str) -> None:
        self._data.pop(pair_id, None)

    def all_pairs(self) -> list[str]:
        return list(self._data.keys())
```

### Pattern 7: FileStore Implementation

```python
# Source: verified by execution — json round-trip with dataclasses.asdict()
import json
from dataclasses import asdict
from pathlib import Path

class FileStore:
    """JSON file-backed trust state store."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._data: dict[str, dict[str, object]] = {}
        if self._path.exists():
            self._load()

    def _load(self) -> None:
        with self._path.open() as f:
            self._data = json.load(f)

    def _save(self) -> None:
        with self._path.open("w") as f:
            json.dump(self._data, f, indent=2)

    def get(self, pair_id: str) -> TrustState | None:
        raw = self._data.get(pair_id)
        if raw is None:
            return None
        return TrustState(**raw)  # type: ignore[arg-type]

    def put(self, pair_id: str, state: TrustState) -> None:
        self._data[pair_id] = asdict(state)
        self._save()

    def delete(self, pair_id: str) -> None:
        self._data.pop(pair_id, None)
        self._save()

    def all_pairs(self) -> list[str]:
        return list(self._data.keys())
```

**Caveat:** `_save()` on every write is correct for simplicity at v0.1.0. For high-throughput use, a write-through cache or explicit flush pattern is better — but that's not in scope.

### Pattern 8: TrustManager Public API

The README and CLAUDE.md agree on this exact API:

```python
class TrustManager:
    def __init__(
        self,
        store: TrustStore | None = None,
        config: TrustConfig | None = None,
    ) -> None:
        self._store = store if store is not None else MemoryStore()
        self._config = config if config is not None else TrustConfig()

    def evaluate(
        self, agent_a: str, agent_b: str, outcome: TrustOutcome
    ) -> TrustState:
        """Record outcome and return updated trust state."""
        ...

    def get_trust_score(self, agent_a: str, agent_b: str) -> float:
        """Return current trust score (0.5 for unknown pairs)."""
        ...

    def should_terminate(self, agent_a: str, agent_b: str) -> bool:
        """Return True if trust score is below the circuit break threshold."""
        ...
```

**Success criterion**: `TrustManager().get_trust_score('a', 'b')` must return `0.5`. This works because unknown pairs return default `TrustState(alpha=1.0, beta=1.0)` and `1.0/(1.0+1.0) == 0.5`.

### Anti-Patterns to Avoid

- **Alpha/beta starting at 0**: `0/(0+0)` is division by zero. Always start at 1.0.
- **Trust formula as Laplace-smoothed `(α+1)/(α+β+2)`**: This is mathematically equivalent when priors are 1.0, but creates confusion. Use raw mean `α/(α+β)` with priors baked into the stored alpha/beta values.
- **Applying decay on write**: Apply decay lazily on read. Writing without elapsed time calculation loses temporal accuracy.
- **Symmetric pair key via string concatenation**: `f"{a}:{b}"` is order-dependent. Always sort first.
- **Storing TrustState as a frozen dataclass**: It needs mutation for performance. Make it mutable and replace on store.
- **Saving FileStore on every read**: Read is idempotent, only save on write.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SHA256 hashing | Custom hash | `hashlib.sha256` | stdlib, tested, collision-resistant |
| JSON serialization | Custom serializer | `json` + `dataclasses.asdict()` | Round-trip verified, no deps |
| File atomicity | Custom write | Not needed at v0.1.0 (write-then-save is fine) | Scope: single-process library |
| Incomplete Beta function (CDF) | Custom numerical integration | Not needed — only mean (`α/(α+β)`) is required | Full CDF only needed for confidence intervals, not in v0.1.0 scope |
| Timestamp management | Custom clock | `time.time()` | Monotonic enough; float seconds since epoch |
| Type checking enforcement | Custom validation | `__post_init__` + `ValueError` | Dataclass post-init is the pattern |

**Key insight:** The Beta distribution trust score only needs the **mean** `α/(α+β)`. The full Beta distribution CDF (which requires the incomplete beta function and continued fractions) is NOT needed for this phase. Avoid implementing it — it's complex numerical code with precision edge cases.

---

## Common Pitfalls

### Pitfall 1: Division by Zero on New Pairs

**What goes wrong:** If alpha=0 and beta=0 (zero prior), `alpha/(alpha+beta)` raises `ZeroDivisionError`.
**Why it happens:** Forgetting to initialize with the uninformative prior.
**How to avoid:** TrustConfig defaults `alpha_prior=1.0, beta_prior=1.0`. TrustManager creates new TrustState with these priors, never with zeros.
**Warning signs:** `ZeroDivisionError` in `trust_score` property; tests on new pairs failing.

### Pitfall 2: Fast Circuit Breaking Surprises

**What goes wrong:** With default `threshold=0.3` and `failure_weight=1.0`, just 2 consecutive failures trigger circuit break (trust drops to 0.25). This is mathematically correct but may surprise users.
**Why it happens:** Small prior (α=1,β=1) means early interactions have outsized influence.
**How to avoid:** Document this explicitly. For real multi-agent scenarios with mixed outcomes, circuit breaking takes many more interactions. The 2-failure case is extreme (100% failure rate). Tests should assert this is the correct behavior, not a bug.
**Warning signs:** Tests expecting "resilient" behavior at low interaction count.

### Pitfall 3: Decay Toward 0 Instead of Toward Prior

**What goes wrong:** Implementing decay as `alpha *= decay_factor` instead of `alpha = 1.0 + (alpha - 1.0) * decay_factor`. Former decays toward 0 (distrust), latter decays toward 1.0 (uncertainty).
**Why it happens:** Naive "exponential decay" thinking.
**How to avoid:** The decay target is the uninformative prior (α=1,β=1), not zero. After many half-lives, trust should converge to 0.5, not 0.0.
**Warning signs:** Success criterion #5 fails: "Trust score decays toward 0.5 (uncertainty)" — if you get 0.0 instead, decay formula is wrong.

### Pitfall 4: Order-Dependent Pair Key

**What goes wrong:** `evaluate("agent-a", "agent-b", ...)` and `evaluate("agent-b", "agent-a", ...)` create two separate trust relationships.
**Why it happens:** Using `f"{a}:{b}"` as the key.
**How to avoid:** Always sort: `":".join(sorted([agent_a, agent_b]))` before hashing.
**Warning signs:** `get_trust_score("a","b") != get_trust_score("b","a")` in tests.

### Pitfall 5: `from __future__ import annotations` + `get_type_hints()` at Runtime

**What goes wrong:** If any code calls `typing.get_type_hints()` on a class decorated with `@dataclass` when `from __future__ import annotations` is in effect, forward references may fail to resolve in Python 3.9.
**Why it happens:** `from __future__ import annotations` makes all annotations lazy strings. At runtime, `get_type_hints()` tries to evaluate them.
**How to avoid:** This library does NOT use `get_type_hints()` internally. External users (e.g., Pydantic, FastAPI dependency injection) may hit this if they introspect the types. For v0.1.0, `from __future__ import annotations` is safe — use it in every file.
**Warning signs:** `NameError` when external frameworks introspect the package's public types.

### Pitfall 6: FileStore Not Atomic

**What goes wrong:** Process interrupted mid-write corrupts the JSON file.
**Why it happens:** `json.dump()` writes incrementally; if interrupted, leaves partial JSON.
**How to avoid:** For v0.1.0, this is acceptable — document it. Mitigation in v0.2.0: write to `.tmp` file then `os.replace()`. Don't over-engineer now.
**Warning signs:** `json.JSONDecodeError` on FileStore initialization.

### Pitfall 7: Confusing `pyproject.toml` `[tool.coverage.report]` vs CLI flags

**What goes wrong:** `fail_under` set in `[tool.coverage.report]` only takes effect when running `coverage report` directly, not always when running via `pytest --cov`.
**How to avoid:** Set threshold in BOTH `[tool.coverage.report]` AND `[tool.pytest.ini_options]` `addopts` as `--cov-fail-under=95`. The flag in `addopts` is authoritative when running pytest.
**Warning signs:** Tests "pass" with 80% coverage because the threshold wasn't applied.

---

## Code Examples

### Complete pyproject.toml

```toml
[build-system]
requires = ["hatchling>=1.21"]
build-backend = "hatchling.build"

[project]
name = "fulcrum-trust"
version = "0.1.0"
description = "Trust-based circuit breaking for multi-agent AI systems"
readme = "README.md"
license = "Apache-2.0"
license-files = ["LICENSE"]
requires-python = ">=3.9"
authors = [
    { name = "Fulcrum", email = "hello@fulcrumlayer.io" },
]
keywords = ["agents", "trust", "circuit-breaker", "langgraph", "multi-agent"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Libraries :: Python Modules",
]
dependencies = []  # zero required runtime deps

[project.optional-dependencies]
numpy = ["numpy>=1.21"]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "mypy>=1.0",
    "ruff>=0.1",
]

[project.urls]
Homepage = "https://github.com/Fulcrum-Governance/fulcrum-trust"
Repository = "https://github.com/Fulcrum-Governance/fulcrum-trust"
Issues = "https://github.com/Fulcrum-Governance/fulcrum-trust/issues"

[tool.hatch.build.targets.wheel]
packages = ["fulcrum_trust"]

# Pytest configuration
[tool.pytest.ini_options]
addopts = [
    "--cov=fulcrum_trust",
    "--cov-report=term-missing",
    "--cov-fail-under=95",
    "--cov-config=pyproject.toml",
]
testpaths = ["tests"]

# Coverage configuration
[tool.coverage.run]
source = ["fulcrum_trust"]
omit = ["fulcrum_trust/adapters/*"]  # adapters have lower threshold (90%)

[tool.coverage.report]
fail_under = 95
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "@(abc\\.)?abstractmethod",
]

# Mypy configuration
[tool.mypy]
python_version = "3.9"
strict = true
warn_return_any = true
warn_unused_configs = true

[[tool.mypy.overrides]]
module = "numpy"
ignore_missing_imports = true

# Ruff configuration
[tool.ruff]
target-version = "py39"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
ignore = ["E501"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

### Optional numpy import pattern (mypy strict safe)

```python
# Source: mypy.readthedocs.io/en/stable/common_issues.html + verified pattern
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np  # Only imported during static analysis

try:
    import numpy as _np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


def compute_decay_factor(elapsed: float, half_life: float) -> float:
    """Compute exponential decay factor. Uses numpy if available."""
    if _HAS_NUMPY:
        return float(_np.power(0.5, elapsed / half_life))  # type: ignore[union-attr]
    return 0.5 ** (elapsed / half_life)  # Pure Python fallback
```

### mypy strict-compliant TrustConfig dataclass

```python
# Source: verified by execution on Python 3.11.13
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TrustConfig:
    """Configuration for the trust engine.

    Args:
        threshold: Circuit break threshold. Trust below this triggers termination.
        half_life_seconds: Half-life for exponential decay. Default = 24 hours.
        alpha_prior: Initial alpha for new agent pairs. Default = 1.0 (uninformative).
        beta_prior: Initial beta for new agent pairs. Default = 1.0 (uninformative).
        success_weight: Alpha increment per SUCCESS outcome.
        failure_weight: Beta increment per FAILURE outcome.
        partial_alpha_weight: Alpha increment per PARTIAL outcome.
        partial_beta_weight: Beta increment per PARTIAL outcome.
    """
    threshold: float = 0.3
    half_life_seconds: float = 86400.0  # 24 hours
    alpha_prior: float = 1.0
    beta_prior: float = 1.0
    success_weight: float = 1.0
    failure_weight: float = 1.0
    partial_alpha_weight: float = 0.5
    partial_beta_weight: float = 0.5

    def __post_init__(self) -> None:
        if not 0.0 < self.threshold < 1.0:
            raise ValueError(
                f"threshold must be in (0, 1), got {self.threshold}"
            )
        if self.half_life_seconds <= 0:
            raise ValueError(
                f"half_life_seconds must be positive, got {self.half_life_seconds}"
            )
```

### Public API __init__.py pattern

```python
# fulcrum_trust/__init__.py
from __future__ import annotations

from fulcrum_trust.manager import TrustManager
from fulcrum_trust.types import TrustConfig, TrustOutcome, TrustState

__all__ = [
    "TrustManager",
    "TrustOutcome",
    "TrustState",
    "TrustConfig",
]

__version__ = "0.1.0"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `setup.py` + `setup.cfg` | `pyproject.toml` + hatchling | PEP 517/518 (2017), widely adopted by 2023 | Single config file, no `setup.py` needed |
| `typing.List`, `typing.Dict` | `list[...]`, `dict[...]` built-in | Python 3.9 (PEP 585) | Drop `from typing import List, Dict` |
| `typing.Optional[X]` | `X | None` | Python 3.10 (PEP 604), usable in 3.9 with `from __future__ import annotations` | Cleaner syntax |
| ABC for interfaces | `typing.Protocol` | Python 3.8 (PEP 544), mature by 3.9 | Structural subtyping, no forced inheritance |
| `flake8` + `isort` + `black` | `ruff` | ruff reached v1.0 stability ~2024 | Single tool, 10-100x faster |
| `.coveragerc` file | `[tool.coverage]` in `pyproject.toml` | coverage 5.0+, common by 2023 | Consolidated config |

**Deprecated/outdated:**
- `typing.List`, `typing.Dict`, `typing.Optional`, `typing.Tuple`: Deprecated in 3.9. Use lowercase builtins or `X | None` with `from __future__ import annotations`.
- `setup.py`: Not needed for pure Python packages with hatchling.
- `.coveragerc` as separate file: Superseded by `[tool.coverage]` in `pyproject.toml`.

---

## Open Questions

1. **Python version: 3.9 minimum or 3.10+?**
   - What we know: CLAUDE.md specifies "Python 3.9+"; `.python-version` = 3.11.13; `plan.md` says "Python >=3.10"
   - What's unclear: Whether the project intends to support 3.9 or silently requires 3.10+ features
   - Recommendation: Set `requires-python = ">=3.9"` in `pyproject.toml` to match CLAUDE.md. Use `from __future__ import annotations` in all files to enable `X | None` syntax on 3.9. Avoid `match` statements and `ParamSpec` (3.10+ only).

2. **Decay application: lazy (on read) or eager (on write)?**
   - What we know: Lazy reads are simpler; eager writes require storing the "effective" state separately
   - What's unclear: Whether TrustManager.evaluate() should apply decay before updating
   - Recommendation: Apply decay lazily at the START of every `evaluate()` call, before applying the new outcome. This ensures the decay is applied before new evidence is recorded.

3. **Thread safety for MemoryStore?**
   - What we know: CLAUDE.md says nothing about threading; single-process library
   - What's unclear: Whether concurrent agent frameworks could call evaluate() from multiple threads
   - Recommendation: Document MemoryStore as NOT thread-safe in v0.1.0. Add a comment pointing to a future `ThreadSafeMemoryStore` if needed. Don't add `threading.Lock` now — it complicates tests.

---

## Sources

### Primary (HIGH confidence)
- Python docs — `dataclasses`, `hashlib`, `json`, `math`, `time`, `typing` modules (all stdlib)
- Python typing spec — Protocol definition and `@runtime_checkable` behavior: https://typing.python.org/en/latest/spec/protocol.html
- mypy docs — strict mode config, `[[tool.mypy.overrides]]` for numpy: https://mypy.readthedocs.io/en/stable/config_file.html
- pytest-cov docs — `--cov-fail-under` flag and `addopts` pattern: https://pytest-cov.readthedocs.io/en/latest/config.html
- Python Packaging User Guide — `pyproject.toml` with hatchling: https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
- Python Packaging — src vs flat layout: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
- Ruff configuration docs: https://docs.astral.sh/ruff/configuration/

### Secondary (MEDIUM confidence)
- `.claude/research.md` — prior domain research: Beta distribution formulas, MAST taxonomy, Python ecosystem notes (verified against README.md)
- Mathematical verification of all formulas executed on Python 3.11.13 (locally verified)

### Tertiary (LOW confidence, needs validation)
- Plan.md states "Python >=3.10" — contradicts CLAUDE.md's "Python 3.9+". Resolution: follow CLAUDE.md as authoritative.
- Thread safety assumptions: no official source; based on standard Python library design norms.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all are stdlib or well-documented PyPI packages
- Architecture: HIGH — verified by executing key patterns on Python 3.11.13
- Beta math: HIGH — formulas executed and validated against documented examples
- Packaging: HIGH — from official Python Packaging User Guide
- Pitfalls: MEDIUM — based on pattern analysis and math verification; thread safety is LOW (convention-based)

**Research date:** 2026-02-18
**Valid until:** 2026-05-18 (stable domain; Python packaging conventions change slowly)
