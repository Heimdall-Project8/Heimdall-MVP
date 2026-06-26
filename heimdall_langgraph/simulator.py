"""
simulator.py — Background thread that continuously generates sensor events.

Completely decoupled from the LangGraph graph.  Runs in a daemon thread,
applies the Tier-1 rule engine locally, and pushes detected anomaly signals
into a thread-safe queue.Queue that the graph polls.

Anomaly rate: ~10% of ticks produce an anomaly (7% tailgating, 3% forced-open)
so you see roughly 1-2 anomalies per 10 normal entries — fast enough to watch
the difference on screen without flooding the LLM.
"""

import queue
import random
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

import database

# ── gates ─────────────────────────────────────────────────────────────────────
GATES      = ["lobby_entrance", "north_gate", "south_gate", "parking_barrier", "server_room_door"]
AUTH_GATES = ["lobby_entrance", "north_gate", "south_gate", "parking_barrier"]
AUTH_TYPES = ["badge_swipe", "camera_scan"]

# ── probability split ─────────────────────────────────────────────────────────
_P_NORMAL   = 0.90
_P_TAILGATE = 0.07   # → 7 in 100 ticks
_P_FORCED   = 0.03   # → 3 in 100 ticks

# ── in-memory gate state (only accessed from simulator thread) ─────────────────
_gate_history: dict[str, dict] = {}


# ── sequence builders ─────────────────────────────────────────────────────────
def _uid() -> str:
    return str(uuid.uuid4())


def _gen_normal(t: datetime, resident_ids: list[str]) -> list[dict]:
    gate = random.choice(AUTH_GATES)
    user = random.choice(resident_ids)
    auth = random.choice(AUTH_TYPES)
    payload = {"status": "success", "user_id": user}
    if auth == "badge_swipe":
        payload["credential_id"] = "rfid_ok"
    else:
        payload["confidence_score"] = f"{random.uniform(0.95, 0.99):.2f}"
    return [
        {"event_id": _uid(), "timestamp": t.isoformat(),                          "gate_id": gate, "event_type": auth,                    "payload": payload},
        {"event_id": _uid(), "timestamp": (t + timedelta(seconds=1)).isoformat(),  "gate_id": gate, "event_type": "door_state_change",     "payload": {"state": "open"}},
        {"event_id": _uid(), "timestamp": (t + timedelta(seconds=2)).isoformat(),  "gate_id": gate, "event_type": "person_counter_update", "payload": {"count": 1}},
    ]


def _gen_tailgating(t: datetime, resident_ids: list[str]) -> list[dict]:
    gate = random.choice(AUTH_GATES)
    user = random.choice(resident_ids)
    auth = random.choice(AUTH_TYPES)
    payload = {"status": "success", "user_id": user}
    if auth == "badge_swipe":
        payload["credential_id"] = "rfid_ok"
    else:
        payload["confidence_score"] = f"{random.uniform(0.95, 0.99):.2f}"
    return [
        {"event_id": _uid(), "timestamp": t.isoformat(),                          "gate_id": gate, "event_type": auth,                    "payload": payload},
        {"event_id": _uid(), "timestamp": (t + timedelta(seconds=1)).isoformat(),  "gate_id": gate, "event_type": "door_state_change",     "payload": {"state": "open"}},
        # 7 s gap > 5 s threshold → triggers tailgating rule
        {"event_id": _uid(), "timestamp": (t + timedelta(seconds=7)).isoformat(),  "gate_id": gate, "event_type": "person_counter_update", "payload": {"count": 2}},
    ]


def _gen_forced_open(t: datetime) -> list[dict]:
    return [
        {"event_id": _uid(), "timestamp": t.isoformat(),                          "gate_id": "server_room_door", "event_type": "door_sensor",            "payload": {"state": "FORCED_OPEN"}},
        {"event_id": _uid(), "timestamp": (t + timedelta(seconds=1)).isoformat(),  "gate_id": "server_room_door", "event_type": "person_counter_update",  "payload": {"count": 1}},
    ]


# ── Tier-1 detector ───────────────────────────────────────────────────────────
def _detect(event: dict) -> Optional[dict]:
    """
    Run one sensor event through the local rule engine.
    Mutates _gate_history.  Returns a signal dict or None.
    """
    gate   = event["gate_id"]
    etype  = event["event_type"]
    payload= event.get("payload", {})
    ts     = event["timestamp"]
    t      = datetime.fromisoformat(ts)

    _gate_history.setdefault(gate, {"last_auth_time": None, "last_user_id": None})

    # track last authenticated user per gate
    if etype in AUTH_TYPES and payload.get("status") == "success":
        _gate_history[gate]["last_auth_time"] = t
        _gate_history[gate]["last_user_id"]   = payload.get("user_id")
        return None

    # tailgating rule
    if etype == "person_counter_update" and payload.get("count", 0) > 1:
        last_auth = _gate_history[gate]["last_auth_time"]
        last_user = _gate_history[gate]["last_user_id"]
        diff      = (t - last_auth).total_seconds() if last_auth else None

        if diff is None or diff > 5.0:
            reason = (
                f"Tailgating — {payload['count']} people entered {diff:.1f}s after badge scan."
                if diff is not None
                else "Tailgating — multiple people entered with no prior authentication."
            )
            sig = {
                "signal_type":         "TAILGATING",
                "gate_id":             gate,
                "timestamp":           ts,
                "reason":              reason,
                "responsible_user_id": last_user,
                "triggering_event_id": event["event_id"],
            }
            # save raw incident to DB immediately (Tier-1 write)
            iid = database.save_tailgating_incident(sig)
            sig["db_id"] = iid
            return sig

    # forced-open rule
    if etype == "door_sensor" and payload.get("state") == "FORCED_OPEN":
        sig = {
            "signal_type":         "DOOR_ALARM",
            "gate_id":             gate,
            "timestamp":           ts,
            "reason":              "Hardware contact sensor registered physical forced entry.",
            "responsible_user_id": None,
            "triggering_event_id": event["event_id"],
        }
        iid = database.save_forced_open_incident(sig)
        sig["db_id"] = iid
        return sig

    return None


# ── log helpers ───────────────────────────────────────────────────────────────
def _fmt(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M:%S")
    except Exception:
        return iso


def _log(event: dict) -> None:
    p = ", ".join(f"{k}:{v}" for k, v in event.get("payload", {}).items())
    print(
        f"  ⚙️  [{_fmt(event['timestamp'])}] "
        f"{event['gate_id']:<18}  "
        f"{event['event_type']:<22}  "
        f"→ {p}"
    )


# ── main simulator loop ───────────────────────────────────────────────────────
def run_simulator(
    anomaly_queue: queue.Queue,
    ready_event:   threading.Event,
    tick_sleep:    float = 0.6,
) -> None:
    """
    Runs forever in a daemon thread.
    Generates one event-sequence per tick, logs every event, and pushes
    any detected anomaly signal into anomaly_queue.
    tick_sleep controls how fast normal entries scroll — lower = faster demo.
    """
    ready_event.wait()
    resident_ids = database.load_resident_ids()
    sim_clock    = datetime.now()
    tick         = 0

    print("🟢 [SIM THREAD] Simulator started — generating events continuously...\n")

    while True:
        sim_clock += timedelta(seconds=random.randint(10, 45))
        tick       += 1
        roll        = random.random()

        if roll < _P_NORMAL:
            sequence = _gen_normal(sim_clock, resident_ids)
            label    = "NORMAL "
        elif roll < _P_NORMAL + _P_TAILGATE:
            sequence = _gen_tailgating(sim_clock, resident_ids)
            label    = "⚠️  TAILGATE"
        else:
            sequence = _gen_forced_open(sim_clock)
            label    = "🔴 FORCED_OPEN"

        print(f"┌─ [SIM tick {tick:04d}] {label}")
        for ev in sequence:
            _log(ev)

        # run Tier-1 detector on each event
        for ev in sequence:
            signal = _detect(ev)
            if signal is not None:
                print(f"│  🚨 ANOMALY DETECTED → {signal['signal_type']} at {signal['gate_id']} | user: {signal.get('responsible_user_id','unknown')}")
                print(f"│  💾 Saved to DB  (id: {signal.get('db_id','?')})")
                print(f"│  📥 Pushed to investigation queue  (depth now: {anomaly_queue.qsize()+1})")
                anomaly_queue.put(signal)

        print(f"└─ queue depth: {anomaly_queue.qsize()}")
        time.sleep(tick_sleep)
