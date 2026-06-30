from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import db
from schema import ResidentRequest
from generator import generate_password

router = APIRouter()


# ---------- Models ----------
class VehicleAdd(BaseModel):
    resident_id: str
    plate_number: str


class VehicleRemove(BaseModel):
    resident_id: str
    plate_number: str


def normalize_plate(plate: str):
    return plate.upper().replace(" ", "").replace("-", "")


# ---------- Get Resident Profile ----------
@router.get("/profile/{resident_id}")
async def get_resident_profile(resident_id: str):

    resident = await db.residents.find_one({
        "id": resident_id
    })

    if not resident:
        raise HTTPException(
            status_code=404,
            detail="Resident not found"
        )

    return {
        "full_name": resident["full_name"],
        "id": resident["id"],
        "flat_number": resident["flat_number"],
        "phone": resident["phone"],
        "badge": resident.get("badge", "Not Assigned"),
        "vehicles": resident.get("vehicles", [])
    }


# ---------- Add Vehicle ----------
@router.post("/add-vehicle")
async def add_vehicle(payload: VehicleAdd):

    resident = await db.residents.find_one({
        "id": payload.resident_id
    })

    if not resident:
        raise HTTPException(
            status_code=404,
            detail="Resident not found"
        )

    normalized_plate = normalize_plate(payload.plate_number)

    existing_vehicle = await db.vehicles.find_one({
        "plate_number": normalized_plate
    })

    if existing_vehicle:
        raise HTTPException(
            status_code=400,
            detail="Vehicle already registered"
        )

    await db.vehicles.insert_one({
        "plate_number": normalized_plate,
        "resident_id": payload.resident_id
    })

    await db.residents.update_one(
        {"id": payload.resident_id},
        {
            "$push": {
                "vehicles": normalized_plate
            }
        }
    )

    return {
        "message": "Vehicle added successfully",
        "plate_number": normalized_plate
    }


# ---------- Remove Vehicle ----------
@router.delete("/remove-vehicle")
async def remove_vehicle(payload: VehicleRemove):

    normalized_plate = normalize_plate(payload.plate_number)

    result = await db.vehicles.delete_one({
        "plate_number": normalized_plate,
        "resident_id": payload.resident_id
    })

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found"
        )

    await db.residents.update_one(
        {"id": payload.resident_id},
        {
            "$pull": {
                "vehicles": normalized_plate
            }
        }
    )

    return {
        "message": "Vehicle removed successfully"
    }


# ---------- Report Lost Card ----------
@router.post("/report-lost-card/{resident_id}")
async def report_lost_card(resident_id: str):

    resident = await db.residents.find_one({
        "id": resident_id
    })

    if not resident:
        raise HTTPException(
            status_code=404,
            detail="Resident not found"
        )

    current_status = resident.get("card_status", "active")

    if current_status == "blocked":
        raise HTTPException(
            status_code=400,
            detail="Card already blocked"
        )

    await db.residents.update_one(
        {"id": resident_id},
        {
            "$set": {
                "card_status": "blocked"
            }
        }
    )

    return {
        "message": "Card blocked successfully. Security notified."
    }


# ---------- Generate Resident Identities (Admin) ----------
@router.post("/generate-identities")
async def generate_identities(data: ResidentRequest):

    existing = await db.residents.find_one(
        {
            "flat_number": data.flat_number
        }
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Flat {data.flat_number} is already registered."
        )

    output = []

    for index, badge in enumerate(data.resident_badge_ids, start=1):

        resident = {
            "id": f"res_{data.flat_number}_{index}",
            "flat_number": data.flat_number,
            "badge": badge,
            "password": generate_password(),
            "full_name": None,
            "age": None,
            "phone": None,
            "is_initialized": False,
            "vehicles": [],
            "card_status": "active"
        }

        await db.residents.insert_one(resident)

        output.append({
            "Resident": "Resident",
            "Password": resident["password"],
            "Badge": resident["badge"],
            "ID": resident["id"],
            "Flat": resident["flat_number"]
        })

    return output