import os
import random
from typing import List
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv
# 1. Import Pydantic for strict schema enforcement
from pydantic import BaseModel, Field, FieldValidationInfo, field_validator

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# --- DEFINING THE PYDANTIC SCHEMAS (Our Safety Net) ---

class FamilyMemberSchema(BaseModel):
    rfid_token: str
    relationship: str

class ResidentSchema(BaseModel):
    id: str = Field(..., alias="_id")  # Maps Python 'id' to MongoDB '_id'
    name: str
    phone_number: str
    age: int
    flat_no: str
    role: str
    associated_credentials: List[str]
    family_members: List[FamilyMemberSchema]
    trust_score: float = 1.0
    status: str = "active"

    # Example of a custom validator: Ensures flat numbers always match your requested format
    @field_validator('flat_no')
    @classmethod
    def validate_flat_format(cls, v: str) -> str:
        if not (v.startswith('{') and v.endswith('}')):
            raise ValueError("Flat number must strictly be wrapped in curly braces like {A-101}")
        return v

# ------------------------------------------------------

FIRST_NAMES = ["Aarav", "Ananya", "Rahul", "Priya", "John", "Jane", "David", "Sarah", "Amit", "Meera", "Vikram", "Sneha"]
LAST_NAMES = ["Sharma", "Patel", "Reddy", "Kumar", "Smith", "Jones", "Verma", "Nair", "Joshi", "Das"]
BLOCKS = ["A", "B", "C"]

def generate_indian_phone():
    first_digit = random.choice(["9", "8", "7", "6"])
    rest = "".join(str(random.randint(0, 9)) for _ in range(9))
    return f"+91{first_digit}{rest}"

def generate_safe_20_residents():
    bulk_operations = []
    
    for i in range(100, 120):
        res_id = f"res_{i}"
        last_name = random.choice(LAST_NAMES)
        full_name = f"{random.choice(FIRST_NAMES)} {last_name}"
        
        assigned_block = random.choice(BLOCKS)
        flat_no_string = f"{{{assigned_block}-{100 + (i - 100)}}}"
        
        family = []
        if random.random() < 0.50:
            family.append({"rfid_token": f"rfid_token_hex_{hex(i)}_spouse", "relationship": "spouse"})
        if i in [100, 101, 102]:
            family.append({"rfid_token": f"rfid_token_hex_{hex(i)}_child_1", "relationship": "child"})

        # 2. We construct the data dictionary
        raw_data = {
            "_id": res_id,
            "name": full_name,
            "phone_number": generate_indian_phone(),
            "age": random.randint(28, 55),
            "flat_no": flat_no_string,
            "role": "resident",
            "associated_credentials": [f"rfid_token_hex_{hex(i)}"],
            "family_members": family
        }
        
        # 3. SAFETY CHECK: Validate data against Pydantic schema
        # If any field is bad, this line crashes immediately and protects MongoDB!
        validated_resident = ResidentSchema(**raw_data)
        
        # Convert validated Pydantic object back into a clean dictionary for MongoDB injection
        bulk_operations.append(
            UpdateOne({"_id": res_id}, {"$set": validated_resident.model_dump(by_alias=True)}, upsert=True)
        )
        
    return bulk_operations

if __name__ == "__main__":
    MONGO_URI = os.getenv("MONGO_URI")
    client = MongoClient(MONGO_URI)
    db = client["heimdall_security"]
    collection = db["residents"]
    
    print("Wiping old collection data for a fresh start...")
    collection.delete_many({}) 
    
    collection.create_index("associated_credentials")
    collection.create_index("family_members.rfid_token")
    
    print("Validating schemas and saving clean structures to Atlas...")
    try:
        operations = generate_safe_20_residents()
        result = collection.bulk_write(operations)
        print("🚀 SUCCESS: 20 Type-Safe Resident Profiles Populated securely!")
    except Exception as e:
        print(f"❌ SCHEMA VALIDATION FAILED: Data was blocked before reaching database.\nDetails: {e}")