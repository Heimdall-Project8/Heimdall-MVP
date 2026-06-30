from fastapi import APIRouter
from datetime import datetime
from zoneinfo import ZoneInfo

from schema import AnnouncementRequest
from database import db

router = APIRouter()


@router.post("/send-announcement")
async def send_announcement(data: AnnouncementRequest):

    announcement = {
        "title": data.title,
        "message": data.message,
        "created_at": datetime.now(ZoneInfo("Asia/Kolkata"))
    }

    await db.announcements.insert_one(announcement)

    return {
        "status": "success",
        "message": "Announcement stored successfully."
    }


@router.get("/announcements")
async def get_announcements():

    announcements = await db.announcements.find(
        {},
        {"_id": 0}
    ).to_list(length=None)

    return announcements