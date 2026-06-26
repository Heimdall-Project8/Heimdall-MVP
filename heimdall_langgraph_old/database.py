import os
import csv
from datetime import datetime, timedelta
from pymongo import MongoClient

# Dynamically construct the path to the root folder (one level up from this file)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CSV_PATH = os.path.join(BASE_DIR, "heimdall_security_residents_actual.csv")

def get_db():
    """Establishes connection to the MongoDB Atlas cluster securely via environment variables."""
    uri = os.getenv("MONGO_URI")
    if not uri:
        raise ValueError("❌ Error: MONGO_URI missing from environment variables!")
    client = MongoClient(uri)
    return client["heimdall_security"]

def load_resident_ids(csv_path=DEFAULT_CSV_PATH):
    """Reads the primary roster CSV file and extracts active resident IDs."""
    ids = []
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"❌ Error: Cannot find CSV file at '{csv_path}'.")
        
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("status", "").strip().lower() == "active":
                ids.append(row.get("_id", "").strip())
    return ids

def get_resident_details(user_id, csv_path=DEFAULT_CSV_PATH):
    """Searches the roster CSV and returns all profile fields for a specific resident."""
    if not user_id:
        return None
        
    if not os.path.exists(csv_path):
        return {"error": f"Resident roster file not found at {csv_path}"}
        
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("_id", "").strip() == str(user_id).strip():
                return {k.strip(): v.strip() for k, v in row.items()}
                
    return {"warning": f"User ID {user_id} was not found in the official resident roster."}

def get_recent_anomalies(gate_id, user_id=None, hours_back=24):
    """Queries MongoDB for historical incidents matching this gate or user within the last 24 hours."""
    db = get_db()
    cutoff_time = (datetime.now() - timedelta(hours=hours_back)).isoformat()
    
    query = {"gate_id": gate_id, "timestamp": {"$gte": cutoff_time}}
    if user_id:
        query["responsible_user_id"] = user_id
        
    tailgating = list(db["Tailgating_incidents"].find(query, {"_id": 0}))
    forced = list(db["Door_Forced_Open_Incidents"].find(query, {"_id": 0}))
    
    return {"past_tailgating_incidents": tailgating, "past_forced_door_incidents": forced}