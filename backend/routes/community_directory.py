from fastapi import APIRouter, HTTPException
from database import db

router = APIRouter()


@router.get("/community-directory")
def get_community_directory():

    residents = db.residents.find(
        {}, {"_id": 0}
    ).to_list(length=None)

    guards = db.security_guards.find(
        {}, {"_id": 0}
    ).to_list(length=None)

    community = []

    # Residents
    for resident in residents:
        community.append({
            "id": resident["id"],
            "name": resident.get("full_name") or resident["id"],
            "role": "Resident",
            "score": resident.get("score", 100),
            "status": "Active",
            "is_initialized": resident.get("is_initialized", False),
            "card_status": resident.get("card_status", "active")
        })

    # Security Guards
    for guard in guards:
        community.append({
            "id": guard["id"],
            "name": guard.get("full_name") or guard["id"],
            "role": "Security",
            "score": guard.get("score", 100),
            "status": "Active",
            "is_initialized": guard.get("is_initialized", False),
            "card_status": guard.get("card_status", "active")
        })

    return community


@router.delete("/resident/{resident_id}")
def delete_resident(resident_id: str):

    result = db.residents.delete_one(
        {"id": resident_id}
    )

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail="Resident not found"
        )

    return {
        "message": "Resident deleted successfully"
    }