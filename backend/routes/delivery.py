from fastapi import APIRouter
from models.delivery import DeliveryEntry
from database import client
from datetime import datetime
from zoneinfo import ZoneInfo

router = APIRouter()

# Access the admin_res database
db = client["admin_res"]


# ---------------------------------------------------
# Get all active deliveries (Security Dashboard)
# ---------------------------------------------------
@router.get("/pending")
async def get_pending_deliveries():

    deliveries = await db.delivery_notifications.find(
        {
            "status": {
                "$in": ["active", "PASSED_GATE"]
            }
        },
        {
            "_id": 0
        }
    ).to_list(length=None)

    return deliveries


# ---------------------------------------------------
# Check deliveries for a specific flat (Optional)
# ---------------------------------------------------
@router.get("/check/{flat_no}")
async def check_delivery(flat_no: str):

    deliveries = await db.delivery_notifications.find(
        {
            "resident_flat": flat_no,
            "status": "active"
        },
        {
            "_id": 0
        }
    ).to_list(length=None)

    if not deliveries:
        return {
            "message": "No active delivery found"
        }

    return deliveries


# ---------------------------------------------------
# Allow delivery entry
# ---------------------------------------------------
@router.post("/allow-entry")
async def allow_entry(data: DeliveryEntry):

    result = await db.delivery_notifications.update_one(
        {
            "delivery_id": data.delivery_id,
            "status": "active"
        },
        {
            "$set": {
                "status": "PASSED_GATE",
                "gate_entry_time": datetime.now(
                    ZoneInfo("Asia/Kolkata")
                ).strftime("%Y-%m-%d %H:%M:%S IST")
            }
        }
    )

    if result.modified_count == 0:
        return {
            "message": "Delivery not found or already processed"
        }

    return {
        "message": "Delivery marked as PASSED_GATE",
        "delivery_id": data.delivery_id
    }