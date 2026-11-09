import os
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
import httpx

from backend.app.core.config import settings
from database.connection import log_event, get_setting

class MetaService:
    def __init__(self):
        self.api_version = settings.META_API_VERSION
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

    async def get_credentials(self) -> Dict[str, Optional[str]]:
        page_id = await get_setting("FACEBOOK_PAGE_ID") or settings.FACEBOOK_PAGE_ID
        page_token = await get_setting("FACEBOOK_PAGE_ACCESS_TOKEN") or settings.FACEBOOK_PAGE_ACCESS_TOKEN
        return {
            "page_id": page_id.strip() if page_id else None,
            "page_token": page_token.strip() if page_token else None
        }

    async def verify_page_access(self, page_id: Optional[str] = None, page_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Verify whether the Facebook Page ID and Page Access Token are valid
        and have 'CREATE_CONTENT' / 'MANAGE' permissions.
        """
        creds = await self.get_credentials()
        pid = page_id or creds["page_id"]
        token = page_token or creds["page_token"]

        if not pid or not token:
            return {
                "valid": False,
                "error": "Missing Page ID or Page Access Token. Please configure them in Settings."
            }

        url = f"{self.base_url}/{pid}"
        params = {
            "fields": "id,name,username,tasks,access_token",
            "access_token": token
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params)
                data = resp.json()

                if resp.status_code != 200 or "error" in data:
                    err = data.get("error", {}).get("message", "Invalid token or permissions")
                    await log_event("FACEBOOK", "ERROR", f"Page verification failed: {err}")
                    return {"valid": False, "error": err}

                page_name = data.get("name", pid)
                tasks = data.get("tasks", [])
                await log_event("FACEBOOK", "INFO", f"Facebook Page verified: {page_name} (ID: {pid})")
                return {
                    "valid": True,
                    "page_id": pid,
                    "page_name": page_name,
                    "tasks": tasks
                }
        except Exception as e:
            return {"valid": False, "error": f"Connection exception: {str(e)}"}

    async def publish_reel(
        self,
        video_path: str,
        title: str,
        caption: str,
        hashtags: str,
        target_page_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Publishes a video to Facebook Reels using official Meta Graph API v21.0:
        1. Initialize session (upload_phase=start)
        2. Upload binary payload to upload_url
        3. Finish & Publish (upload_phase=finish)
        4. Poll processing status
        """
        creds = await self.get_credentials()
        page_id = target_page_id or creds["page_id"]
        page_token = creds["page_token"]

        if not page_id or not page_token:
            err_msg = "Cannot publish: Facebook Page ID or Access Token is not configured."
            await log_event("FACEBOOK", "ERROR", err_msg)
            return {
                "success": False,
                "error": err_msg,
                "needs_configuration": True
            }

        video_file = Path(video_path)
        if not video_file.exists():
            return {"success": False, "error": f"Video file not found at: {video_path}"}

        file_size = video_file.stat().st_size
        full_description = f"{caption}\n\n{hashtags}".strip()

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                # Step 1: Initialize Reels Upload Session
                await log_event("FACEBOOK", "INFO", f"Initializing Reels upload session for Page {page_id}")
                init_url = f"{self.base_url}/{page_id}/video_reels"
                init_payload = {
                    "upload_phase": "start",
                    "access_token": page_token
                }
                
                resp = await client.post(init_url, data=init_payload)
                init_data = resp.json()

                if resp.status_code != 200 or "video_id" not in init_data:
                    err_msg = init_data.get("error", {}).get("message", resp.text)
                    await log_event("FACEBOOK", "ERROR", f"Failed to start Reels session: {err_msg}")
                    return {"success": False, "error": f"Phase 1 (Start) failed: {err_msg}"}

                video_id = init_data["video_id"]
                upload_url = init_data["upload_url"]

                # Step 2: Upload Video Binary Chunks
                await log_event("FACEBOOK", "INFO", f"Uploading binary stream for video ID {video_id} ({file_size / (1024*1024):.1f} MB)")
                with open(video_file, "rb") as vf:
                    upload_headers = {
                        "Authorization": f"OAuth {page_token}",
                        "offset": "0",
                        "file_size": str(file_size)
                    }
                    upload_resp = await client.post(upload_url, headers=upload_headers, content=vf.read())

                if upload_resp.status_code not in (200, 201):
                    err_msg = upload_resp.text
                    await log_event("FACEBOOK", "ERROR", f"Failed video upload transfer: {err_msg}")
                    return {"success": False, "error": f"Phase 2 (Transfer) failed: {err_msg}"}

                # Step 3: Finish and Publish Reel
                await log_event("FACEBOOK", "INFO", f"Publishing Reel {video_id}...")
                finish_payload = {
                    "upload_phase": "finish",
                    "access_token": page_token,
                    "video_id": video_id,
                    "video_state": "PUBLISHED",
                    "description": full_description
                }
                finish_resp = await client.post(init_url, data=finish_payload)
                finish_data = finish_resp.json()

                if finish_resp.status_code != 200 or not finish_data.get("success", False):
                    err_msg = finish_data.get("error", {}).get("message", finish_resp.text)
                    await log_event("FACEBOOK", "ERROR", f"Failed finish phase: {err_msg}")
                    return {"success": False, "error": f"Phase 3 (Finish) failed: {err_msg}"}

                # Step 4: Check status & construct link
                reel_url = f"https://www.facebook.com/reel/{video_id}"
                post_id = finish_data.get("post_id", f"{page_id}_{video_id}")

                await log_event(
                    "FACEBOOK",
                    "SUCCESS",
                    f"Successfully published Reel! ID: {video_id}",
                    {"video_id": video_id, "reel_url": reel_url, "post_id": post_id}
                )

                return {
                    "success": True,
                    "video_id": video_id,
                    "post_id": post_id,
                    "reel_url": reel_url
                }

            except Exception as e:
                await log_event("FACEBOOK", "ERROR", f"Exception during Reels publishing: {str(e)}")
                return {"success": False, "error": str(e)}
