from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import db

# Existing routes
from routes.auth import router as auth_router
from routes.visitor import router as visitor_router
from routes.qr import router as qr_router
from routes.resident import router as resident_router

# New admin routes
from routes.security_guard import router as security_router
from routes.announcement import router as announcement_router
from routes.community_directory import router as community_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication
app.include_router(auth_router, prefix="/auth")

# Visitor
app.include_router(visitor_router, prefix="/visitor")

# QR
app.include_router(qr_router, prefix="/qr")

# Resident
app.include_router(resident_router, prefix="/resident")

# Security Guards
app.include_router(security_router, prefix="/security")

# Announcements
app.include_router(announcement_router, prefix="/announcement")

# Community Directory
app.include_router(community_router, prefix="/community")


@app.get("/")
async def root():
    resident_count = await db.residents.count_documents({})

    return {
        "message": "Heimdall FastAPI server running",
        "resident_count": resident_count
    }