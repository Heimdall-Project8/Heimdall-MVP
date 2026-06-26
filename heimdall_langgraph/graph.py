"""
graph.py — Heimdall LangGraph pipeline entry point.

Architecture:
  ┌──────────────────────────────────────────┐
  │  Background thread  (simulator.py)        │
  │  generates events → Tier-1 detects        │
  │  → pushes anomalies into anomaly_queue    │
  └──────────────────────┬───────────────────┘
                         │  queue.Queue (thread-safe)
                         ▼
  ┌──────────────────────────────────────────┐
  │  LangGraph loop  (this file)              │
  │                                           │
  │   pull from queue                         │
  │       ↓                                   │
  │   investigate_node  (Gemini LLM)          │
  │       ↓                                   │
  │   dispatch_node  (trust score + DB save)  │
  │       ↓                                   │
  │   loop back → pull next from queue        │
  └──────────────────────────────────────────┘

The simulator never pauses — it keeps generating while the LLM is thinking.
Any anomalies that arrive during LLM inference sit in the queue and are
processed in FIFO order.
"""

import os
import queue
import sqlite3
import threading
import time

from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

import database
from nodes import dispatch_node, investigate_node
from simulator import run_simulator
from state import SecurityState

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))

POLL_INTERVAL = float(os.getenv("HEIMDALL_POLL_INTERVAL", "0.5"))  # seconds between queue polls


# ── graph builder ─────────────────────────────────────────────────────────────
def build_graph():
    wf = StateGraph(SecurityState)
    wf.add_node("investigate", investigate_node)
    wf.add_node("dispatch",    dispatch_node)

    wf.set_entry_point("investigate")
    wf.add_edge("investigate", "dispatch")

    # after dispatch: if more alerts queued in state, keep dispatching
    def _after_dispatch(state: SecurityState) -> str:
        return "investigate" if state.get("investigation_results") else END

    wf.add_conditional_edges("dispatch", _after_dispatch, {"investigate": "investigate", END: END})

    db_conn = sqlite3.connect(
        os.path.join(os.path.dirname(__file__), "heimdall_persistence.db"),
        check_same_thread=False,
    )
    return wf.compile(checkpointer=SqliteSaver(db_conn))


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("═" * 70)
    print("  🛡️  HEIMDALL — Physical Access Security AI Pipeline  v2")
    print("  Simulator: background thread  |  Brain: Gemini 2.5 Flash")
    print("═" * 70)

    # validate setup
    try:
        resident_ids = database.load_resident_ids()
        print(f"✅ Resident roster: {len(resident_ids)} active residents loaded")
    except Exception as exc:
        print(f"❌ {exc}")
        raise SystemExit(1)

    # thread-safe anomaly queue shared between simulator thread and main loop
    anomaly_queue: queue.Queue = queue.Queue()
    ready_event:   threading.Event = threading.Event()

    # start simulator in daemon thread — dies automatically when main exits
    sim_thread = threading.Thread(
        target=run_simulator,
        args=(anomaly_queue, ready_event),
        kwargs={"tick_sleep": float(os.getenv("HEIMDALL_TICK_SLEEP", "0.6"))},
        daemon=True,
        name="heimdall-simulator",
    )
    sim_thread.start()
    ready_event.set()   # release the simulator

    app    = build_graph()
    config = {"configurable": {"thread_id": "heimdall_main"}}

    print("\n✅ LangGraph pipeline ready")
    print("✅ Simulator thread live — watch the stream below")
    print("   (Press Ctrl+C to shut down cleanly)\n")
    print("─" * 70)

    # ── main polling loop ──────────────────────────────────────────────────
    # We don't use app.stream() here because we need to block on the external
    # queue rather than on LangGraph's own state transitions.
    # Instead we manually invoke the graph each time a new anomaly arrives.

    episodic_messages: list = []   # carry messages across invocations

    try:
        while True:
            try:
                signal = anomaly_queue.get(timeout=POLL_INTERVAL)
            except queue.Empty:
                continue

            print(f"\n⚡ [MAIN LOOP] Anomaly pulled from queue → {signal['signal_type']} @ {signal['gate_id']}")
            print(f"   Queue depth remaining: {anomaly_queue.qsize()}")

            initial_state: SecurityState = {
                "anomaly_queue":         [signal],
                "investigation_results": [],
                "messages":              episodic_messages,
            }

            final_state = app.invoke(initial_state, config)

            # carry episodic memory forward to next invocation
            episodic_messages = final_state.get("messages", [])
            # cap memory at last 20 messages to avoid prompt bloat
            if len(episodic_messages) > 20:
                episodic_messages = episodic_messages[-20:]

            anomaly_queue.task_done()

    except KeyboardInterrupt:
        print("\n🛑 Shutdown signal received. Heimdall pipeline halted cleanly.")
