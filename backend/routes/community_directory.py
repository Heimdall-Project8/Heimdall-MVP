from fastapi import APIRouter, HTTPException

from database import db

router = APIRouter()


@router.get("/community-directory")
async def get_community_directory():

    residents = await db.residents.find(
        {}, {"_id": 0}
    ).to_list(length=None)

    guards = await db.security_guards.find(
        {}, {"_id": 0}
    ).to_list(length=None)

    community = []

    # Residents
    for resident in residents:
        community.append({
            "id": resident["id"],
            "name": resident.get("full_name") or resident["id"],
            "role": "Resident",
            "score": 100,
            "status": "Active"
        })

    # Security Guards
    for guard in guards:
        community.append({
            "id": guard["id"],
            "name": guard.get("full_name") or guard["id"],
            "role": "Security",
            "score": 100,
            "status": "Active"
        })

    return community


@router.delete("/resident/{resident_id}")
async def delete_resident(resident_id: str):

    result = await db.residents.delete_one(
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