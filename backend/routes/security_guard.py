from fastapi import APIRouter

from schema import SecurityGuardRequest
from database import db
from generator import generate_password

router = APIRouter()


@router.post("/generate-security-guards")
async def generate_security_guards(data: SecurityGuardRequest):

    output = []

    start_id = 101

    while await db.security_guards.find_one(
        {"id": f"guard_{start_id}"}
    ):
        start_id += 1

    for i in range(data.number_of_new_guards):

        guard_id = start_id + i

        guard = {
            "id": f"guard_{guard_id}",
            "password": generate_password(),
            "full_name": None,
            "age": None,
            "phone": None,
            "is_initialized": False
        }

        await db.security_guards.insert_one(guard)

        output.append({
            "Security": "Security",
            "ID": guard["id"],
            "Password": guard["password"]
        })

    return output