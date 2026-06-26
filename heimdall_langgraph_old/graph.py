import sqlite3
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
import nodes
from dotenv import load_dotenv
import os
from state import SecurityState

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))

# Conditional routing routers
def route_after_detection(state: SecurityState):
    if state.get("tick", 0) > 40: # Stream limits for presentation execution 
        return END
    if len(state.get("anomaly_queue", [])) > 0:
        return "investigate"
    return "simulate"

def route_after_dispatch(state: SecurityState):
    if len(state.get("anomaly_queue", [])) > 0:
        return "investigate"
    return "simulate"

# Instantiating the graph
workflow = StateGraph(SecurityState)

# Attaching workers
workflow.add_node("simulate", nodes.generate_event_node)
workflow.add_node("detect", nodes.detect_and_route_node)
workflow.add_node("investigate", nodes.investigate_node)
workflow.add_node("dispatch", nodes.format_and_dispatch_node)

# Wiring topology
workflow.set_entry_point("simulate")
workflow.add_edge("simulate", "detect")

workflow.add_conditional_edges(
    "detect",
    route_after_detection,
    {"investigate": "investigate", "simulate": "simulate", END: END}
)

workflow.add_edge("investigate", "dispatch")

workflow.add_conditional_edges(
    "dispatch",
    route_after_dispatch,
    {"investigate": "investigate", "simulate": "simulate"}
)

# Compile using persistent file memory instead of volatile RAM savers
db_connection = sqlite3.connect("heimdall_persistence.db", check_same_thread=False)
memory_checkpointer = SqliteSaver(db_connection)
app = workflow.compile(checkpointer=memory_checkpointer)

if __name__ == "__main__":
    
    import time
    
    # Load .env variables from parent directory root path
    
    
    print("🛡️ Heimdall Guard Agent State Engine initialized successfully.")
    print("Monitoring live stream sequences... Press Ctrl+C to terminate application.\n")
    
    config = {"configurable": {"thread_id": "facility_main_stream"}}
    initial_runtime_state = {
        "tick": 0, 
        "current_sequence": [], 
        "anomaly_queue": [], 
        "investigation_results": [],
        "messages": []
    }
    
    # Execute the runtime engine stream loop
    try:
        for event in app.stream(initial_runtime_state, config, stream_mode="values"):
            # Internal execution loop logging is handled directly inside nodes for structural visibility
            time.sleep(0.4)
    except KeyboardInterrupt:
        print("\nShutdown command captured. Gracefully exiting telemetry capture.")