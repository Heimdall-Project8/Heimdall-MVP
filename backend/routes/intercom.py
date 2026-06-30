from fastapi import APIRouter
from models.intercom import IntercomRequest
from database import security_db
from bson import ObjectId
from datetime import datetime
from zoneinfo import ZoneInfo

router = APIRouter()


@router.post("/call")
async def call_resident(data: IntercomRequest):

    call_data = data.model_dump(exclude={"call_id"})

    call_data["status"] = "DIALING"

    result = await secuirty_db.intercom_calls.insert_one(call_data)

    return {
        "message": "Call dialing",
        "call_id": str(result.inserted_id)
    }


@router.post("/connect")
async def connect_call(data: IntercomRequest):

    ist_time = datetime.now(
        ZoneInfo("Asia/Kolkata")
    ).strftime("%Y-%m-%d %H:%M:%S IST")

    await security_db.intercom_calls.update_one(
        {"_id": ObjectId(data.call_id)},
        {
            "$set": {
                "status": "CONNECTED",
                "startedAt": ist_time
            }
        }
    )

    return {
        "message": "Call connected"
    }


@router.post("/end-call")
async def end_call(data: IntercomRequest):

    started_call = await security_db.intercom_calls.find_one(
        {
            "_id": ObjectId(data.call_id)
        }
    )

    if not started_call:
        return {
            "message": "Call not found"
        }

    started_at = datetime.strptime(
        started_call["startedAt"],
        "%Y-%m-%d %H:%M:%S IST"
    )

    ended_at = datetime.now(ZoneInfo("Asia/Kolkata"))
    ended_at_str = ended_at.strftime("%Y-%m-%d %H:%M:%S IST")

    duration = int(
        (
            ended_at.replace(tzinfo=None) - started_at
        ).total_seconds()
    )

    await secuirty_db.intercom_calls.update_one(
        {
            "_id": ObjectId(data.call_id)
        },
        {
            "$set": {
                "status": "ENDED",
                "endedAt": ended_at_str,
                "duration": duration
            }
        }
    )

    return {
        "message": "Call ended"
    }