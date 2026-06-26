import random
import uuid
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 1. Force Python to find the .env file in the folder one level up
env_path = os.path.join(os.path.dirname(__file__), "../.env")
load_dotenv(dotenv_path=env_path)

# 2. Explicitly grab the key from the environment
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError(f"❌ CRITICAL ERROR: Could not find the API key. Please check that your .env file is located at {env_path} and contains GEMINI_API_KEY=your_key")

from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
import database
from state import SecurityState

# 3. Explicitly pass the key into the LangChain model
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", 
    temperature=0.1,
    api_key=api_key
)

class SecurityAlert(BaseModel):
    severity: str = Field(description="Calculated danger classification. Must be exactly 'Low', 'Medium', or 'High'")
    summary: str = Field(description="Detailed narrative correlating user details, DB history, and immediate threat telemetry.")
    target_interface: str = Field(description="Target destination channel. Must be exactly 'Resident', 'Guard', or 'Supervisor'")

structured_llm = llm.with_structured_output(SecurityAlert)

# --- NODE 1: SIMULATOR ---
def generate_event_node(state: SecurityState):
    """Generates sensor telemetry streams targeting a ~1-in-35 structural anomaly occurrence trend."""
    resident_ids = database.load_resident_ids()
    simulated_clock = datetime.now()
    roll = random.random()
    sequence = []
    
    if roll < 0.941:  # Normal Entry sequence
        user = random.choice(resident_ids)
        sequence = [
            {"gate_id": "lobby_entrance", "event_type": "badge_swipe", "payload": {"status": "success", "user_id": user}, "timestamp": simulated_clock.isoformat()},
            {"gate_id": "lobby_entrance", "event_type": "door_state_change", "payload": {"state": "open"}, "timestamp": (simulated_clock + timedelta(seconds=1)).isoformat()},
            {"gate_id": "lobby_entrance", "event_type": "person_counter_update", "payload": {"count": 1}, "timestamp": (simulated_clock + timedelta(seconds=2)).isoformat()}
        ]
    elif roll < 0.971:  # Tailgating anomaly sequence
        user = random.choice(resident_ids)
        sequence = [
            {"gate_id": "north_gate", "event_type": "badge_swipe", "payload": {"status": "success", "user_id": user}, "timestamp": simulated_clock.isoformat()},
            {"gate_id": "north_gate", "event_type": "door_state_change", "payload": {"state": "open"}, "timestamp": (simulated_clock + timedelta(seconds=1)).isoformat()},
            {"gate_id": "north_gate", "event_type": "person_counter_update", "payload": {"count": 2}, "timestamp": (simulated_clock + timedelta(seconds=6)).isoformat()}
        ]
    else:  # Hardware Door Forced open sequence
        sequence = [
            {"gate_id": "server_room_door", "event_type": "door_sensor", "payload": {"state": "FORCED_OPEN"}, "timestamp": simulated_clock.isoformat()},
            {"gate_id": "server_room_door", "event_type": "person_counter_update", "payload": {"count": 1}, "timestamp": (simulated_clock + timedelta(seconds=1)).isoformat()}
        ]
        
    # Print the live stream so the terminal isn't completely silent
    for event in sequence:
        time_str = datetime.fromisoformat(event["timestamp"]).strftime("%H:%M:%S")
        print(f"⚙️ [LOG] [{time_str}] | Place: {event['gate_id']:<15} | Event: {event['event_type']:<20}")
        
    return {"current_sequence": sequence, "tick": state.get("tick", 0) + 1}

# --- NODE 2: DETECTOR FILTER ---
def detect_and_route_node(state: SecurityState):
    """Algorithmic filtering: Saves anomalies to DB and pushes them to the state queue."""
    sequence = state.get("current_sequence", [])
    anomalies = []
    db = database.get_db()
    
    is_tailgating = any(e.get("event_type") == "person_counter_update" and e.get("payload", {}).get("count", 0) > 1 for e in sequence)
    is_forced = any(e.get("payload", {}).get("state") == "FORCED_OPEN" for e in sequence)
    
    auth_event = next((e for e in sequence if e.get("event_type") == "badge_swipe"), None)
    user_id = auth_event["payload"]["user_id"] if auth_event else None
    gate_id = sequence[0]["gate_id"] if sequence else "unknown"

    if is_tailgating:
        signal = {"signal_type": "TAILGATING", "gate_id": gate_id, "responsible_user_id": user_id, "timestamp": datetime.now().isoformat()}
        db["Tailgating_incidents"].insert_one(signal.copy()) # Write to cloud collection
        anomalies.append(signal)

    elif is_forced:
        signal = {"signal_type": "DOOR_ALARM", "gate_id": gate_id, "responsible_user_id": None, "timestamp": datetime.now().isoformat()}
        db["Door_Forced_Open_Incidents"].insert_one(signal.copy()) # Write to cloud collection
        anomalies.append(signal)

    updated_queue = state.get("anomaly_queue", []) + anomalies
    return {"anomaly_queue": updated_queue, "current_sequence": []}

# --- NODE 3: INVESTIGATOR (LLM Brain) ---
def investigate_node(state: SecurityState):
    """Pops an anomaly, fetches rich cross-context data, and uses Gemini to analyze patterns."""
    queue = state.get("anomaly_queue", [])
    if not queue:
        return {}
        
    incident = queue.pop(0)  # FIFO queue management
    user_id = incident.get("responsible_user_id")
    gate_id = incident.get("gate_id")
    
    # Context aggregation layer
    history = database.get_recent_anomalies(gate_id, user_id)
    user_profile = database.get_resident_details(user_id) if user_id else None
    
    system_prompt = """You are Heimdall AI, a Tier-2 Security Investigator. 
    Analyze the current anomaly alongside database history, user profiles, and your conversation memory.
    
    CLASSIFICATION PROTOCOLS:
    - Low Severity: Active residents who tailgate. (Likely friends, moving items, family). Route to 'Resident'.
    - Medium Severity: Repeated resident violations within 24 hours, or an unknown/unauthenticated individual tailgating standard gates. Route to 'Guard'.
    - High Severity: Physical forced break-ins ('DOOR_ALARM'), inactive user credentials, or multiple distinct anomalies cascading sequentially (e.g., tailgating through a door that was forced open). Route to 'Supervisor'.
    
    Cross-reference your episodic conversational memory array. If you recognize a repeating pattern that hasn't cleared out of memory, escalate the threat context immediately."""
    
    payload = {
        "target_anomaly": incident,
        "responsible_party_profile": user_profile if user_profile else "No credential authentication trace found.",
        "historical_db_context_24h": history
    }
    
    print(f"\n🔍 [INVESTIGATING] {incident['signal_type']} detected at {gate_id}...")
    result: SecurityAlert = structured_llm.invoke([
        SystemMessage(content=system_prompt),
        *state.get("messages", []),  # Inject memory history
        HumanMessage(content=f"Analyze context packet:\n{json.dumps(payload, default=str, indent=2)}")
    ])
    
    new_results = state.get("investigation_results", []) + [result.dict()]
    memory_update = HumanMessage(content=f"Logged alert summary: [{result.severity}] at {gate_id} by party {user_id or 'Unknown'}. Summary: {result.summary}")
    
    return {"anomaly_queue": queue, "investigation_results": new_results, "messages": [memory_update]}

# --- NODE 4: DISPATCHER ---
def format_and_dispatch_node(state: SecurityState):
    """Extracts processed alerts from state and routes them cleanly to their specific dashboard interfaces."""
    results = state.get("investigation_results", [])
    if not results:
        return {}
        
    alert = results.pop(0)
    
    print("\n📡 " + "═"*55)
    print(f"  HEIMDALL ACTIVE DISPATCH ALERT: [{alert['severity'].upper()}]")
    print(f"  Target UI Dashboard: {alert['target_interface']}")
    print(f"  AI Diagnostic: {alert['summary']}")
    print("═"*57 + "\n")
    
    return {"investigation_results": results}