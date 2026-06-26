from typing import TypedDict, List, Dict, Any
from typing_extensions import Annotated
from langgraph.graph.message import add_messages

class SecurityState(TypedDict):
    tick: int                                # Infinite loop guard for simulation streaming
    current_sequence: List[Dict[str, Any]]   # Current event sequence evaluated by Tier-1
    anomaly_queue: List[Dict[str, Any]]      # Buffer holding detected anomalies awaiting evaluation
    investigation_results: List[Dict[str, Any]] # Output payload container for alerts
    messages: Annotated[list, add_messages]  # Chat message history (short-term episodic memory)