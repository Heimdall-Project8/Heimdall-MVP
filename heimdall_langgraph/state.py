"""
state.py — Shared graph state for the Heimdall investigation pipeline.

The simulator runs in a background thread and is NOT part of the graph.
The graph only handles: pull anomaly → investigate → dispatch → loop.
"""

from typing import Any, Dict, List, Optional
from typing_extensions import Annotated, TypedDict
from langgraph.graph.message import add_messages


class SecurityState(TypedDict, total=False):
    # ── investigation pipeline ─────────────────────────────────────────────
    anomaly_queue:         List[Dict[str, Any]]      # anomalies pulled from the thread-safe queue
    investigation_results: List[Dict[str, Any]]      # completed alert payloads
    # ── episodic memory (append-only, LangGraph managed) ──────────────────
    messages: Annotated[list, add_messages]
