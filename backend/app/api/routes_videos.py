import json
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from database.connection import get_db, log_event
from database.models import VideoRecord
from services.meta_service import MetaService
from backend.app.core.config import settings

router = APIRouter(prefix="/api/videos", tags=["Videos"])
meta_service = MetaService()

class VideoUpdatePayload(BaseModel):
    caption_title: Optional[str] = None
    caption_body: Optional[str] = None
    hashtags: Optional[str] = None

@router.get("")
async def list_videos(limit: int = 50, db: AsyncSession = Depends(get_db)):
    stmt = select(VideoRecord).order_by(desc(VideoRecord.created_at)).limit(limit)
    res = await db.execute(stmt)
    records = res.scalars().all()

    items = []
    for r in records:
        ai_data = {}
        if r.ai_analysis:
            try:
                ai_data = json.loads(r.ai_analysis)
            except Exception:
                ai_data = {"raw": r.ai_analysis}

        items.append({
            "id": r.id,
            "gdrive_file_id": r.gdrive_file_id,
            "file_name": r.file_name,
            "file_size": r.file_size,
            "duration_seconds": r.duration_seconds,
            "resolution": r.resolution,
            "status": r.status,
            "thumbnail_url": f"/api/videos/{r.id}/thumbnail" if r.thumbnail_path else None,
            "ai_analysis": ai_data,
            "caption_title": r.caption_title,
            "caption_body": r.caption_body,
            "hashtags": r.hashtags,
            "facebook_page_id": r.facebook_page_id,
            "facebook_video_id": r.facebook_video_id,
            "facebook_post_id": r.facebook_post_id,
            "facebook_reel_url": r.facebook_reel_url,
            "error_message": r.error_message,
            "retry_count": r.retry_count,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "published_at": r.published_at.isoformat() if r.published_at else None
        })
    return items

@router.get("/{video_id}")
async def get_video_detail(video_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(VideoRecord).where(VideoRecord.id == video_id)
    res = await db.execute(stmt)
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Video record not found")

    ai_data = {}
    if r.ai_analysis:
        try:
            ai_data = json.loads(r.ai_analysis)
        except Exception:
            pass

    return {
        "id": r.id,
        "gdrive_file_id": r.gdrive_file_id,
        "file_name": r.file_name,
        "file_size": r.file_size,
        "duration_seconds": r.duration_seconds,
        "resolution": r.resolution,
        "status": r.status,
        "thumbnail_url": f"/api/videos/{r.id}/thumbnail" if r.thumbnail_path else None,
        "ai_analysis": ai_data,
        "caption_title": r.caption_title,
        "caption_body": r.caption_body,
        "hashtags": r.hashtags,
        "facebook_reel_url": r.facebook_reel_url,
        "error_message": r.error_message,
        "retry_count": r.retry_count,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "published_at": r.published_at.isoformat() if r.published_at else None
    }

@router.get("/{video_id}/thumbnail")
async def get_video_thumbnail(video_id: str, db: AsyncSession = Depends(get_db)):
    thumb_path = settings.THUMBNAILS_DIR / f"thumb_{video_id}.jpg"
    if thumb_path.exists():
        return FileResponse(thumb_path, media_type="image/jpeg")
    
    # Return placeholder 1x1 GIF if missing
    transparent_gif = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
    return Response(content=transparent_gif, media_type="image/gif")

@router.put("/{video_id}")
async def update_video_content(video_id: str, payload: VideoUpdatePayload, db: AsyncSession = Depends(get_db)):
    stmt = select(VideoRecord).where(VideoRecord.id == video_id)
    res = await db.execute(stmt)
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Video record not found")

    if payload.caption_title is not None:
        r.caption_title = payload.caption_title
    if payload.caption_body is not None:
        r.caption_body = payload.caption_body
    if payload.hashtags is not None:
        r.hashtags = payload.hashtags

    await db.commit()
    return {"success": True, "message": "Updated video captions successfully"}

@router.post("/{video_id}/publish")
async def publish_video_now(video_id: str, db: AsyncSession = Depends(get_db)):
    """
    Manually triggers publishing this specific video to Facebook Reels.
    """
    stmt = select(VideoRecord).where(VideoRecord.id == video_id)
    res = await db.execute(stmt)
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Video record not found")

    if not r.local_path or not Path(r.local_path).exists():
        raise HTTPException(status_code=400, detail="Local video file missing or deleted by cleanup")

    r.status = "POSTING"
    await db.commit()

    pub_res = await meta_service.publish_reel(
        video_path=r.local_path,
        title=r.caption_title or r.file_name,
        caption=r.caption_body or "",
        hashtags=r.hashtags or ""
    )

    if pub_res.get("success"):
        r.status = "PUBLISHED"
        r.facebook_video_id = pub_res.get("video_id")
        r.facebook_post_id = pub_res.get("post_id")
        r.facebook_reel_url = pub_res.get("reel_url")
        r.error_message = None
        await db.commit()
        return {"success": True, "reel_url": r.facebook_reel_url}
    else:
        r.status = "FAILED"
        r.error_message = pub_res.get("error", "Failed to publish")
        r.retry_count += 1
        await db.commit()
        return {"success": False, "error": r.error_message}
