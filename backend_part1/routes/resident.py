from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import db
from datetime import datetime, timedelta

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

    # Check duplicate in vehicles collection
    existing_vehicle = await db.vehicles.find_one({
        "plate_number": normalized_plate
    })

    if existing_vehicle:
        raise HTTPException(
            status_code=400,
            detail="Vehicle already registered"
        )

    # Add to vehicles collection
    await db.vehicles.insert_one({
        "plate_number": normalized_plate,
        "resident_id": payload.resident_id
    })

    # Add to resident document
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

    # Remove from vehicles collection
    result = await db.vehicles.delete_one({
        "plate_number": normalized_plate,
        "resident_id": payload.resident_id
    })

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found"
        )

    # Remove from resident document
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

    await db.security_alerts.insert_one({
        "type": "lost_card",
        "resident_id": resident_id,
        "badge": resident["badge"],
        "message": "Lost card reported",
        "resolved": False
    })

    return {
        "message": "Card blocked successfully. Security notified."
    }


@router.get("/announcements")
async def get_recent_announcements():

    cutoff = datetime.now() - timedelta(hours=24)

    announcements = await db.announcements_collection.find({
        "created_at": {"$gte": cutoff}
    }).sort("created_at", -1).to_list(length=50)

    result = []

    for ann in announcements:
        result.append({
            "title": ann["title"],
            "message": ann["message"],
            "created_at": ann["created_at"]
        })

    return {
        "announcements": result
    }
