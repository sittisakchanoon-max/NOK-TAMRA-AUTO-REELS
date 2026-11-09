import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import settings
from database.connection import init_db, log_event
from workers.scheduler import scheduler_instance

from backend.app.api.routes_dashboard import router as dashboard_router
from backend.app.api.routes_videos import router as videos_router
from backend.app.api.routes_settings import router as settings_router
from backend.app.api.routes_logs import router as logs_router

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("[INIT] Initializing Database...")
    await init_db()
    await log_event("SYSTEM", "INFO", "NOK TAMRA AUTO REELS engine booted")
    
    # Start Scheduler
    print("[INIT] Starting Background Automation Scheduler...")
    await scheduler_instance.start()
    
    yield
    
    # Shutdown
    print("[SHUTDOWN] Shutting down scheduler...")
    scheduler_instance.scheduler.shutdown()

app = FastAPI(
    title="NOK TAMRA AUTO REELS",
    description="Fully Automated AI Facebook Reels Publishing Platform",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(dashboard_router)
app.include_router(videos_router)
app.include_router(settings_router)
app.include_router(logs_router)

# Mount frontend static files
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
