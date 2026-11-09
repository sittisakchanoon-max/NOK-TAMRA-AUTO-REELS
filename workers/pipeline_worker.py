import json
import asyncio
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import select, or_

from backend.app.core.config import settings
from database.connection import AsyncSessionLocal, log_event, get_setting
from database.models import VideoRecord
from services.gdrive_service import GDriveService
from services.video_service import VideoService
from services.ai_service import AIService
from services.meta_service import MetaService
from storage.manager import StorageManager

class PipelineWorker:
    def __init__(self):
        self.gdrive_service = GDriveService()
        self.video_service = VideoService()
        self.ai_service = AIService()
        self.meta_service = MetaService()
        self.storage_manager = StorageManager()
        self._is_running = False

    async def run_pipeline_cycle(self) -> Dict[str, Any]:
        """
        Executes a complete scan and processing cycle.
        Safe concurrency guard included.
        """
        if self._is_running:
            await log_event("WORKER", "WARNING", "Pipeline cycle already in progress, skipping duplicate trigger.")
            return {"status": "skipped", "message": "Already running"}

        self._is_running = True
        stats = {
            "discovered": 0,
            "downloaded": 0,
            "analyzed": 0,
            "published": 0,
            "errors": 0
        }

        try:
            # 1. Fetch configured Drive folder ID
            folder_id = await get_setting("GDRIVE_FOLDER_ID", settings.GDRIVE_FOLDER_ID)
            await log_event("WORKER", "INFO", f"Starting 15-min automation scan for folder: {folder_id}")

            # 2. List videos from Google Drive
            drive_videos = await self.gdrive_service.list_videos(folder_id)
            stats["discovered"] = len(drive_videos)

            if not drive_videos:
                await log_event("WORKER", "INFO", "No video files found in Google Drive folder.")
                return stats

            # 3. Process each video
            async with AsyncSessionLocal() as session:
                for v in drive_videos:
                    file_id = v["id"]
                    file_name = v["name"]

                    # Check if already processed
                    stmt = select(VideoRecord).where(VideoRecord.gdrive_file_id == file_id)
                    res = await session.execute(stmt)
                    existing_record = res.scalar_one_or_none()

                    if existing_record and existing_record.status in ("PUBLISHED", "READY_TO_POST", "ANALYZING"):
                        # Already handled
                        continue

                    if not existing_record:
                        # Create new record
                        video_rec = VideoRecord(
                            gdrive_file_id=file_id,
                            file_name=file_name,
                            mime_type=v.get("type", "video/mp4"),
                            status="PENDING"
                        )
                        session.add(video_rec)
                        await session.commit()
                        await session.refresh(video_rec)
                    else:
                        video_rec = existing_record

                    # Step 3a: Download
                    video_rec.status = "DOWNLOADING"
                    await session.commit()

                    dl_result = await self.gdrive_service.download_video(file_id, file_name)
                    if not dl_result:
                        video_rec.status = "FAILED"
                        video_rec.error_message = "Failed to download from Google Drive"
                        video_rec.retry_count += 1
                        await session.commit()
                        stats["errors"] += 1
                        continue

                    # Check for duplicate hash
                    video_rec.local_path = dl_result["local_path"]
                    video_rec.file_size = dl_result["file_size"]
                    video_rec.file_hash = dl_result["file_hash"]

                    # Check if another record has the exact same hash
                    hash_stmt = select(VideoRecord).where(
                        VideoRecord.file_hash == dl_result["file_hash"],
                        VideoRecord.id != video_rec.id,
                        VideoRecord.status == "PUBLISHED"
                    )
                    hash_res = await session.execute(hash_stmt)
                    duplicate = hash_res.scalar_one_or_none()
                    if duplicate:
                        video_rec.status = "SKIPPED"
                        video_rec.error_message = f"Duplicate video hash matching existing Reel: {duplicate.file_name}"
                        await session.commit()
                        await log_event("WORKER", "WARNING", f"Skipping duplicate video {file_name}")
                        continue

                    stats["downloaded"] += 1

                    # Step 3b: Video Metadata & Frames Extraction
                    video_rec.status = "ANALYZING"
                    await session.commit()

                    meta = await self.video_service.get_metadata(video_rec.local_path)
                    video_rec.duration_seconds = meta.get("duration", 0)
                    video_rec.resolution = meta.get("resolution", "")

                    thumb_path = await self.video_service.extract_thumbnail(video_rec.local_path, video_rec.id)
                    video_rec.thumbnail_path = thumb_path

                    frame_paths = await self.video_service.extract_multi_frames(video_rec.local_path, video_rec.id, count=5)
                    audio_path = await self.video_service.extract_audio(video_rec.local_path, video_rec.id)

                    # Step 3c: AI Multimodal Analysis & Thai Caption Generation
                    ai_result = await self.ai_service.analyze_and_generate(
                        file_name=file_name,
                        frame_paths=frame_paths,
                        audio_path=audio_path,
                        duration=video_rec.duration_seconds or 0
                    )

                    video_rec.ai_analysis = json.dumps(ai_result.get("analysis", {}), ensure_ascii=False)
                    video_rec.caption_title = ai_result.get("caption_title", file_name)
                    video_rec.caption_body = ai_result.get("caption_body", "")
                    video_rec.hashtags = ai_result.get("hashtags", "#NOKTAMRA #ReelsTH")
                    video_rec.status = "READY_TO_POST"
                    await session.commit()
                    stats["analyzed"] += 1

                    # Step 3d: Check Auto-Publish
                    auto_pub_str = await get_setting("AUTO_PUBLISH", "false")
                    auto_pub = (auto_pub_str.lower() == "true") or settings.AUTO_PUBLISH

                    if auto_pub:
                        # Check Facebook credentials
                        creds = await self.meta_service.get_credentials()
                        if creds.get("page_id") and creds.get("page_token"):
                            video_rec.status = "POSTING"
                            await session.commit()

                            pub_res = await self.meta_service.publish_reel(
                                video_path=video_rec.local_path,
                                title=video_rec.caption_title or file_name,
                                caption=video_rec.caption_body or "",
                                hashtags=video_rec.hashtags or "",
                                target_page_id=creds["page_id"]
                            )

                            if pub_res.get("success"):
                                video_rec.status = "PUBLISHED"
                                video_rec.facebook_page_id = creds["page_id"]
                                video_rec.facebook_video_id = pub_res.get("video_id")
                                video_rec.facebook_post_id = pub_res.get("post_id")
                                video_rec.facebook_reel_url = pub_res.get("reel_url")
                                video_rec.published_at = datetime.datetime.utcnow()
                                stats["published"] += 1
                            else:
                                video_rec.status = "FAILED"
                                video_rec.error_message = pub_res.get("error", "Unknown publishing error")
                                stats["errors"] += 1
                        else:
                            await log_event(
                                "WORKER",
                                "INFO",
                                f"Video {file_name} is READY_TO_POST, waiting for Facebook Page credentials in Settings."
                            )

                    await session.commit()

            # 4. Storage cleanup
            await self.storage_manager.cleanup_old_files(days=settings.AUTO_CLEANUP_AFTER_DAYS)

        except Exception as e:
            await log_event("WORKER", "ERROR", f"Error in pipeline cycle: {str(e)}")
            stats["errors"] += 1
        finally:
            self._is_running = False

        return stats
