import os
import re
import json
import hashlib
import asyncio
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from backend.app.core.config import settings
from database.connection import log_event

class GDriveService:
    def __init__(self, folder_id: Optional[str] = None):
        self.folder_id = folder_id or settings.GDRIVE_FOLDER_ID
        self.downloads_dir = settings.DOWNLOADS_DIR

    async def list_videos(self, target_folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all video files (mp4, mov, m4v) in the specified Google Drive folder.
        Uses gdrive CLI or REST API.
        """
        folder = target_folder_id or self.folder_id
        if not folder:
            await log_event("DRIVE", "WARNING", "No Google Drive folder ID specified")
            return []

        # Run gdrive readonly ls
        cmd = ["gdrive", "readonly", "ls", folder]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                err_msg = stderr.decode().strip()
                await log_event("DRIVE", "ERROR", f"Failed to list folder {folder}: {err_msg}")
                return []

            lines = stdout.decode().strip().split("\n")
            if len(lines) <= 2:
                # No files or only header
                return []

            results = []
            # Line format: ID (col 0-33), Name, Type, Size
            for line in lines[2:]:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(maxsplit=3)
                if len(parts) >= 2:
                    file_id = parts[0].strip()
                    file_name = parts[1].strip()
                    # If line has type and size, extract them
                    file_type = parts[2].strip() if len(parts) >= 3 else "unknown"
                    file_size = parts[3].strip() if len(parts) >= 4 else "0 B"
                    
                    # Filter for video extensions
                    ext = Path(file_name).suffix.lower()
                    if ext in [".mp4", ".mov", ".m4v", ".webm"]:
                        results.append({
                            "id": file_id,
                            "name": file_name,
                            "type": file_type,
                            "size_str": file_size,
                            "extension": ext
                        })

            await log_event("DRIVE", "INFO", f"Discovered {len(results)} videos in folder {folder}")
            return results

        except Exception as e:
            await log_event("DRIVE", "ERROR", f"Exception while listing folder {folder}: {str(e)}")
            return []

    async def download_video(self, file_id: str, file_name: str) -> Optional[Dict[str, Any]]:
        """
        Downloads a video file from Google Drive to local storage and calculates SHA-256.
        """
        safe_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', file_name)
        target_path = self.downloads_dir / f"{file_id}_{safe_name}"

        # If already exists and has size > 0
        if target_path.exists() and target_path.stat().st_size > 1024:
            file_hash = self._calculate_sha256(target_path)
            return {
                "local_path": str(target_path),
                "file_size": target_path.stat().st_size,
                "file_hash": file_hash
            }

        tmp_path = self.downloads_dir / f"tmp_{file_id}_{safe_name}"
        if tmp_path.exists():
            tmp_path.unlink()

        await log_event("DRIVE", "INFO", f"Starting download: {file_name} (ID: {file_id})")
        
        cmd = ["gdrive", "readonly", "download", file_id, "--out", str(tmp_path)]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                err_msg = stderr.decode().strip()
                await log_event("DRIVE", "ERROR", f"Download failed for {file_name}: {err_msg}")
                if tmp_path.exists():
                    tmp_path.unlink()
                return None

            if not tmp_path.exists() or tmp_path.stat().st_size == 0:
                await log_event("DRIVE", "ERROR", f"Downloaded file is empty or missing: {file_name}")
                return None

            # Move tmp to target
            tmp_path.rename(target_path)
            file_size = target_path.stat().st_size
            file_hash = self._calculate_sha256(target_path)

            await log_event(
                "DRIVE", 
                "SUCCESS", 
                f"Successfully downloaded {file_name} ({file_size / (1024*1024):.1f} MB)",
                {"file_id": file_id, "size_bytes": file_size, "hash": file_hash}
            )

            return {
                "local_path": str(target_path),
                "file_size": file_size,
                "file_hash": file_hash
            }

        except Exception as e:
            await log_event("DRIVE", "ERROR", f"Exception during download of {file_name}: {str(e)}")
            if tmp_path.exists():
                tmp_path.unlink()
            return None

    def _calculate_sha256(self, filepath: Path) -> str:
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
