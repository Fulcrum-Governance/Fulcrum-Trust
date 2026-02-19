from __future__ import annotations

try:
    from langgraph.graph import StateGraph as _SG  # noqa: F401

    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False

if _LANGGRAPH_AVAILABLE:
    from fulcrum_trust.adapters.langgraph import TrustAwareGraph  # noqa: F401

__all__ = ["TrustAwareGraph"] if _LANGGRAPH_AVAILABLE else []
