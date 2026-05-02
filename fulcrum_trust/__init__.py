from __future__ import annotations

from fulcrum_trust.ipc.bridge import CircuitState, IPCBridge, NullBridge
from fulcrum_trust.ipc.redis_bridge import RedisIPCBridge
from fulcrum_trust.manager import TrustManager

# RLMPrototype is exported as a Phase 5 prototype — API surface is not stable.
# See docs/rlm-python-prototype.md and the class docstring for status.
from fulcrum_trust.rlm import ContextExhausted, RecallBenchmarkResult, RLMPrototype
from fulcrum_trust.stores.file import FileStore
from fulcrum_trust.stores.fulcrum import FulcrumStore
from fulcrum_trust.stores.memory import MemoryStore
from fulcrum_trust.types import TrustCircuitOpen, TrustConfig, TrustOutcome, TrustState

__version__ = "0.2.0"

__all__ = [
    "CircuitState",
    "ContextExhausted",
    "FileStore",
    "FulcrumStore",
    "IPCBridge",
    "MemoryStore",
    "NullBridge",
    "RedisIPCBridge",
    "RLMPrototype",
    "RecallBenchmarkResult",
    "TrustCircuitOpen",
    "TrustConfig",
    "TrustManager",
    "TrustOutcome",
    "TrustState",
]
