from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.core.security import mask_secret
from database.connection import get_setting, set_setting, log_event
from services.meta_service import MetaService
from services.gdrive_service import GDriveService
from storage.manager import StorageManager
from workers.scheduler import scheduler_instance

router = APIRouter(prefix="/api/settings", tags=["Settings"])
meta_service = MetaService()
gdrive_service = GDriveService()
storage_manager = StorageManager()

class SettingsUpdatePayload(BaseModel):
    gdrive_folder_id: Optional[str] = None
    gdrive_check_interval_minutes: Optional[int] = None
    facebook_page_id: Optional[str] = None
    facebook_page_access_token: Optional[str] = None
    gemini_api_key: Optional[str] = None
    auto_publish: Optional[bool] = None

@router.get("")
async def get_all_settings():
    folder_id = await get_setting("GDRIVE_FOLDER_ID", settings.GDRIVE_FOLDER_ID)
    interval = await get_setting("GDRIVE_CHECK_INTERVAL_MINUTES", str(settings.GDRIVE_CHECK_INTERVAL_MINUTES))
    fb_page_id = await get_setting("FACEBOOK_PAGE_ID", settings.FACEBOOK_PAGE_ID or "")
    fb_token = await get_setting("FACEBOOK_PAGE_ACCESS_TOKEN", settings.FACEBOOK_PAGE_ACCESS_TOKEN or "")
    gemini_key = await get_setting("GEMINI_API_KEY", settings.GEMINI_API_KEY or "")
    auto_pub_str = await get_setting("AUTO_PUBLISH", "false")
    auto_publish = (auto_pub_str.lower() == "true") or settings.AUTO_PUBLISH

    return {
        "gdrive_folder_id": folder_id,
        "gdrive_check_interval_minutes": int(interval) if interval.isdigit() else 15,
        "facebook_page_id": fb_page_id,
        "facebook_page_access_token_masked": mask_secret(fb_token),
        "facebook_page_access_token_set": bool(fb_token),
        "gemini_api_key_masked": mask_secret(gemini_key),
        "gemini_api_key_set": bool(gemini_key),
        "auto_publish": auto_publish
    }

@router.post("")
async def update_settings(payload: SettingsUpdatePayload):
    if payload.gdrive_folder_id is not None:
        await set_setting("GDRIVE_FOLDER_ID", payload.gdrive_folder_id.strip())
    
    if payload.gdrive_check_interval_minutes is not None:
        val = max(1, min(1440, payload.gdrive_check_interval_minutes))
        await set_setting("GDRIVE_CHECK_INTERVAL_MINUTES", str(val))
        await scheduler_instance.update_interval(val)

    if payload.facebook_page_id is not None:
        await set_setting("FACEBOOK_PAGE_ID", payload.facebook_page_id.strip())

    if payload.facebook_page_access_token is not None and payload.facebook_page_access_token.strip():
        await set_setting("FACEBOOK_PAGE_ACCESS_TOKEN", payload.facebook_page_access_token.strip())

    if payload.gemini_api_key is not None and payload.gemini_api_key.strip():
        await set_setting("GEMINI_API_KEY", payload.gemini_api_key.strip())

    if payload.auto_publish is not None:
        await set_setting("AUTO_PUBLISH", "true" if payload.auto_publish else "false")

    await log_event("SYSTEM", "SUCCESS", "Settings updated from Dashboard")
    return {"success": True, "message": "Settings saved successfully"}

@router.post("/test-facebook")
async def test_facebook_connection():
    res = await meta_service.verify_page_access()
    return res

@router.post("/test-drive")
async def test_drive_connection():
    folder_id = await get_setting("GDRIVE_FOLDER_ID", settings.GDRIVE_FOLDER_ID)
    videos = await gdrive_service.list_videos(folder_id)
    return {
        "connected": len(videos) > 0,
        "folder_id": folder_id,
        "video_count": len(videos),
        "sample_files": [v["name"] for v in videos[:5]]
    }

@router.get("/storage")
async def get_storage_info():
    return storage_manager.get_storage_stats()

@router.post("/cleanup-storage")
async def trigger_cleanup():
    removed = await storage_manager.cleanup_old_files(days=0, force_cleanup_mb=True)
    return {"success": True, "removed_files": removed}
