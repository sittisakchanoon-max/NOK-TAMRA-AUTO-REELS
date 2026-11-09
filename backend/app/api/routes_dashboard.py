import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database.connection import get_db, get_setting
from database.models import VideoRecord
from backend.app.core.config import settings
from workers.scheduler import scheduler_instance
from services.meta_service import MetaService
from services.gdrive_service import GDriveService

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])
meta_service = MetaService()
gdrive_service = GDriveService()

@router.get("/stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    # 1. Total counts
    stmt_total = select(func.count(VideoRecord.id))
    total_videos = (await db.execute(stmt_total)).scalar() or 0

    stmt_pending = select(func.count(VideoRecord.id)).where(VideoRecord.status.in_(["PENDING", "DOWNLOADING"]))
    pending_videos = (await db.execute(stmt_pending)).scalar() or 0

    stmt_analyzed = select(func.count(VideoRecord.id)).where(VideoRecord.status == "READY_TO_POST")
    analyzed_videos = (await db.execute(stmt_analyzed)).scalar() or 0

    stmt_published = select(func.count(VideoRecord.id)).where(VideoRecord.status == "PUBLISHED")
    published_videos = (await db.execute(stmt_published)).scalar() or 0

    stmt_failed = select(func.count(VideoRecord.id)).where(VideoRecord.status == "FAILED")
    failed_videos = (await db.execute(stmt_failed)).scalar() or 0

    # 2. Check Facebook & Google Drive integration status
    fb_creds = await meta_service.get_credentials()
    fb_connected = bool(fb_creds["page_id"] and fb_creds["page_token"])

    folder_id = await get_setting("GDRIVE_FOLDER_ID", settings.GDRIVE_FOLDER_ID)
    drive_connected = bool(folder_id)

    # 3. Scheduler status
    sched_status = scheduler_instance.get_status()

    # 4. Auto-publish setting
    auto_pub_str = await get_setting("AUTO_PUBLISH", "false")
    auto_publish = (auto_pub_str.lower() == "true") or settings.AUTO_PUBLISH

    return {
        "status": "ONLINE",
        "system_time": datetime.datetime.utcnow().isoformat(),
        "google_drive": {
            "status": "CONNECTED" if drive_connected else "NOT_CONFIGURED",
            "folder_id": folder_id
        },
        "facebook_page": {
            "status": "CONNECTED" if fb_connected else "NOT_CONFIGURED",
            "page_id": fb_creds["page_id"]
        },
        "scheduler": sched_status,
        "auto_publish": auto_publish,
        "metrics": {
            "total_videos": total_videos,
            "pending_videos": pending_videos,
            "analyzed_videos": analyzed_videos,
            "published_videos": published_videos,
            "failed_videos": failed_videos
        }
    }

@router.post("/trigger")
async def trigger_manual_check():
    """
    Manually triggers the Google Drive -> AI -> Publish pipeline immediately.
    """
    result = await scheduler_instance.trigger_now()
    return {"success": True, "result": result}
