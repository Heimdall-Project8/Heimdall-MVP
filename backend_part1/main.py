from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import db
from routes.auth import router as auth_router
from routes.visitor import router as visitor_router
from routes.qr import router as qr_router
from routes.resident import router as resident_router

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

app.include_router(auth_router, prefix="/auth")
app.include_router(visitor_router, prefix="/visitor")
app.include_router(qr_router, prefix="/qr")
app.include_router(resident_router, prefix="/resident")


@app.get("/")
async def root():
    resident_count = await db.residents.count_documents({})

    return {
        "message": "Heimdall FastAPI server running",
        "resident_count": resident_count
    }
