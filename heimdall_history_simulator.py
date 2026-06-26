"""
Heimdall Security — Historical Incident Backfill Simulator
============================================================
Generates a believable HISTORY of access events (normal entries, tailgating
breaches, forced-door intrusions) spread across past dates, runs them through
the same Tier-1 detector logic as the live pipeline, and bulk-pushes only the
detected ANOMALIES into local or cloud MongoDB — split into their own collections.
Regular/normal entries are simulated in-memory to drive the detector but are
never written to the database.

Collections written:
  - Tailgating_incidents          → TAILGATING signals
  - Door_Forced_Open_Incidents    → DOOR_ALARM (forced-open) signals
"""

import argparse
import csv
import json
import os
import random
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv

try:
    from pymongo import MongoClient
except ImportError as e:
    raise SystemExit(
        "pymongo is not installed. Run:\n"
        "    pip install pymongo --break-system-packages\n"
        "then re-run this script."
    ) from e

# Automatically load the .env configuration file located in the same root folder
load_dotenv()

GATES = ["lobby_entrance", "north_gate", "server_room_door"]
AUTH_TYPES = ["badge_swipe", "camera_scan"]  # Dual credential methods


# =====================================================================
# 0. LOAD RESIDENTS FROM CSV
# =====================================================================
def load_resident_ids(csv_path, active_only=True):
    """Reads the resident roster CSV and returns the list of valid _id values."""
    ids = []
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"❌ Error: Cannot find CSV file at '{csv_path}'. Please place it in this folder.")
        
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rid = (row.get("_id") or "").strip()
            status = (row.get("status") or "").strip().lower()
            if not rid:
                continue
            if active_only and status != "active":
                continue
            ids.append(rid)
    if not ids:
        raise ValueError(f"No usable resident IDs found in {csv_path}")
    return ids


# =====================================================================
# 1. RANDOM HISTORICAL TIMESTAMPS
# =====================================================================
def random_past_timestamp(days_back, now=None):
    """Returns a random datetime uniformly distributed somewhere in the past."""
    now = now or datetime.now()
    earliest = now - timedelta(days=days_back)
    span_seconds = int((now - earliest).total_seconds())
    offset = random.randint(0, span_seconds)
    return earliest + timedelta(seconds=offset)


# =====================================================================
# 2. SCENARIO GENERATORS
# =====================================================================
def generate_normal_entry(base_time, resident_ids):
    gate = random.choice(GATES)
    user_id = random.choice(resident_ids)
    auth_event = random.choice(AUTH_TYPES)

    payload = {"status": "success", "user_id": user_id}
    if auth_event == "badge_swipe":
        payload["credential_id"] = "rfid_ok"
    else:
        payload["confidence_score"] = f"{random.uniform(0.95, 0.99):.2f}"

    return [
        {"event_id": str(uuid.uuid4()), "timestamp": base_time.isoformat(), "gate_id": gate, "event_type": auth_event, "payload": payload},
        {"event_id": str(uuid.uuid4()), "timestamp": (base_time + timedelta(seconds=1)).isoformat(), "gate_id": gate, "event_type": "door_state_change", "payload": {"state": "open"}},
        {"event_id": str(uuid.uuid4()), "timestamp": (base_time + timedelta(seconds=2)).isoformat(), "gate_id": gate, "event_type": "person_counter_update", "payload": {"count": 1}},
    ]


def generate_tailgating_incident(base_time, resident_ids):
    gate = random.choice(GATES)
    user_id = random.choice(resident_ids)
    auth_event = random.choice(AUTH_TYPES)

    payload = {"status": "success", "user_id": user_id}
    if auth_event == "badge_swipe":
        payload["credential_id"] = "rfid_ok"
    else:
        payload["confidence_score"] = f"{random.uniform(0.95, 0.99):.2f}"

    return [
        {"event_id": str(uuid.uuid4()), "timestamp": base_time.isoformat(), "gate_id": gate, "event_type": auth_event, "payload": payload},
        {"event_id": str(uuid.uuid4()), "timestamp": (base_time + timedelta(seconds=1)).isoformat(), "gate_id": gate, "event_type": "door_state_change", "payload": {"state": "open"}},
        {"event_id": str(uuid.uuid4()), "timestamp": (base_time + timedelta(seconds=6)).isoformat(), "gate_id": gate, "event_type": "person_counter_update", "payload": {"count": 2}},
    ]


def generate_door_forced_incident(base_time, resident_ids):
    gate = "server_room_door"
    return [
        {"event_id": str(uuid.uuid4()), "timestamp": base_time.isoformat(), "gate_id": gate, "event_type": "door_sensor", "payload": {"state": "FORCED_OPEN"}},
        {"event_id": str(uuid.uuid4()), "timestamp": (base_time + timedelta(seconds=1)).isoformat(), "gate_id": gate, "event_type": "person_counter_update", "payload": {"count": 1}},
    ]


# =====================================================================
# 3. TIER-1 DETECTOR LOGIC
# =====================================================================
def build_detector(tailgating_out, forced_open_out):
    gate_history = {}

    def trigger_candidate_signal(signal_type, gate_id, reason, trigger_event, current_time, responsible_user_id=None):
        signal = {
            "status": "CANDIDATE_SIGNAL",
            "incident_created": True,
            "signal_type": signal_type,
            "gate_id": gate_id,
            "timestamp": current_time.isoformat(),
            "reason": reason,
        }
        if responsible_user_id:
            signal["responsible_user_id"] = responsible_user_id
        signal["triggering_event"] = trigger_event

        if signal_type == "TAILGATING":
            tailgating_out.append(signal)
        elif signal_type == "DOOR_ALARM":
            forced_open_out.append(signal)

    def process_event(event):
        gate_id = event.get("gate_id")
        event_type = event.get("event_type")
        payload = event.get("payload", {})
        current_time = datetime.fromisoformat(event.get("timestamp"))

        if gate_id not in gate_history and gate_id is not None:
            gate_history[gate_id] = {"last_auth_time": None, "last_user_id": None}

        if event_type in AUTH_TYPES and payload.get("status") == "success":
            gate_history[gate_id]["last_auth_time"] = current_time
            gate_history[gate_id]["last_user_id"] = payload.get("user_id")

        elif event_type == "person_counter_update":
            count = payload.get("count", 0)
            if count > 1:
                last_auth = gate_history[gate_id]["last_auth_time"]
                responsible_user = gate_history[gate_id]["last_user_id"]

                if last_auth is None:
                    trigger_candidate_signal(
                        "TAILGATING", gate_id,
                        "Multiple people entered but no authentication records found.",
                        event, current_time,
                    )
                else:
                    time_diff = (current_time - last_auth).total_seconds()
                    if time_diff > 5.0:
                        reason_msg = f"Tailgating breach. Entry detected {time_diff}s after authorization."
                        trigger_candidate_signal(
                            "TAILGATING", gate_id, reason_msg, event, current_time,
                            responsible_user_id=responsible_user,
                        )

        elif event_type == "door_sensor":
            if payload.get("state") == "FORCED_OPEN":
                trigger_candidate_signal(
                    "DOOR_ALARM", gate_id,
                    "Hardware contact sensor registers physical forced break-in.",
                    event, current_time,
                )

    return process_event


# =====================================================================
# 4. BUILD THE FULL HISTORICAL EVENT STREAM
# =====================================================================
def build_event_stream(num_sequences, days_back, resident_ids):
    base_times = sorted(random_past_timestamp(days_back) for _ in range(num_sequences))

    all_events = []
    for base_time in base_times:
        roll = random.random()
        if roll < 0.94:
            sequence = generate_normal_entry(base_time, resident_ids)
        elif roll < 0.98:
            sequence = generate_tailgating_incident(base_time, resident_ids)
        else:
            sequence = generate_door_forced_incident(base_time, resident_ids)
        all_events.extend(sequence)

    return all_events


# =====================================================================
# 5. MAIN — Secure Cloud Execution Engine
# =====================================================================
def main():
    parser = argparse.ArgumentParser(description="Backfill historical Heimdall anomaly incidents into MongoDB.")
    parser.add_argument("--csv", default="heimdall_security_residents_actual.csv", help="Path to residents roster CSV")
    
    # Securely pulls the cluster URI directly out of your active configuration environment
    parser.add_argument("--mongo-uri", default=os.getenv("MONGO_URI"), help="MongoDB connection URI")
    
    parser.add_argument("--db", default="heimdall_security", help="MongoDB database name")
    parser.add_argument("--tailgating-collection", default="Tailgating_incidents", help="Collection for tailgating signals")
    parser.add_argument("--forced-open-collection", default="Door_Forced_Open_Incidents", help="Collection for forced-open door signals")
    parser.add_argument("--days-back", type=int, default=90, help="How many days into the past to spread events across")
    parser.add_argument("--num-events", type=int, default=500, help="Number of entry sequences to generate")
    parser.add_argument("--include-inactive-residents", action="store_true", help="Also allow non-active residents as actors")
    parser.add_argument("--drop", action="store_true", help="Drop existing incident collections before inserting")
    args = parser.parse_args()

    # Integrity Check: Ensure our connection target exists
    if not args.mongo_uri:
        print("❌ ERROR: MONGO_URI not found! Make sure your '.env' file is in this folder and contains your Atlas connection string.")
        return

    try:
        resident_ids = load_resident_ids(args.csv, active_only=not args.include_inactive_residents)
    except Exception as error_msg:
        print(error_msg)
        return

    print(f"Loaded {len(resident_ids)} resident IDs from {args.csv}")
    print(f"Generating {args.num_events} historical sequences spread over the last {args.days_back} days...")
    
    events = build_event_stream(args.num_events, args.days_back, resident_ids)
    print(f"Generated {len(events)} raw events (in-memory parsing active).")

    tailgating_incidents = []
    forced_open_incidents = []
    process_event = build_detector(tailgating_incidents, forced_open_incidents)
    
    for event in events:
        process_event(event)
        
    print(f"Tier-1 detector flagged {len(tailgating_incidents)} tailgating signals "
          f"and {len(forced_open_incidents)} forced-open signals.")

    print("Connecting securely to MongoDB Atlas Cluster...")
    client = MongoClient(args.mongo_uri)
    db = client[args.db]

    if args.drop:
        print("Wiping old collection data for a fresh start...")
        db[args.tailgating_collection].drop()
        db[args.forced_open_collection].drop()
        print(f"Dropped existing '{args.tailgating_collection}' and '{args.forced_open_collection}' collections.")

    if tailgating_incidents:
        db[args.tailgating_collection].insert_many(tailgating_incidents)
    if forced_open_incidents:
        db[args.forced_open_collection].insert_many(forced_open_incidents)

    print(f"🚀 SUCCESS: Inserted {len(tailgating_incidents)} incidents into cloud cluster -> {args.db}.{args.tailgating_collection}")
    print(f"🚀 SUCCESS: Inserted {len(forced_open_incidents)} incidents into cloud cluster -> {args.db}.{args.forced_open_collection}")
    print("Regular/normal entries were not pushed to MongoDB, per request.")
    client.close()


if __name__ == "__main__":
    main()