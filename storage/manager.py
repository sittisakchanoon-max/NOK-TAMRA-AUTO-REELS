import os
import shutil
import time
from pathlib import Path
from typing import Dict, Any
from backend.app.core.config import settings
from database.connection import log_event

class StorageManager:
    def __init__(self):
        self.downloads_dir = settings.DOWNLOADS_DIR
        self.thumbnails_dir = settings.THUMBNAILS_DIR
        self.max_mb = settings.MAX_STORAGE_MB

    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Calculates size of downloads, thumbnails, and free disk space.
        """
        def dir_size_mb(path: Path) -> float:
            total = 0
            if path.exists():
                for p in path.glob("**/*"):
                    if p.is_file():
                        total += p.stat().st_size
            return round(total / (1024 * 1024), 2)

        downloads_mb = dir_size_mb(self.downloads_dir)
        thumbnails_mb = dir_size_mb(self.thumbnails_dir)
        
        # Disk usage of volume
        stat = shutil.disk_usage(settings.STORAGE_DIR)
        disk_free_mb = round(stat.free / (1024 * 1024), 2)
        disk_total_mb = round(stat.total / (1024 * 1024), 2)

        return {
            "downloads_mb": downloads_mb,
            "thumbnails_mb": thumbnails_mb,
            "used_total_mb": round(downloads_mb + thumbnails_mb, 2),
            "max_allowed_mb": self.max_mb,
            "disk_free_mb": disk_free_mb,
            "disk_total_mb": disk_total_mb,
            "percentage_used": min(100.0, round(((downloads_mb + thumbnails_mb) / max(1, self.max_mb)) * 100, 1))
        }

    async def cleanup_old_files(self, days: int = 3, force_cleanup_mb: bool = False) -> int:
        """
        Removes temporary video downloads older than `days` or if quota exceeded.
        """
        cutoff_seconds = time.time() - (days * 86400)
        removed_count = 0
        removed_bytes = 0

        stats = self.get_storage_stats()
        is_over_quota = stats["used_total_mb"] > self.max_mb

        if not self.downloads_dir.exists():
            return 0

        for f in self.downloads_dir.glob("*"):
            if f.is_file() and f.name != ".gitkeep":
                mtime = f.stat().st_mtime
                if mtime < cutoff_seconds or (force_cleanup_mb and is_over_quota):
                    try:
                        sz = f.stat().st_size
                        f.unlink()
                        removed_count += 1
                        removed_bytes += sz
                    except Exception as e:
                        print(f"Error removing {f}: {e}")

        if removed_count > 0:
            mb_freed = round(removed_bytes / (1024 * 1024), 2)
            await log_event(
                "SYSTEM",
                "INFO",
                f"Storage cleanup: removed {removed_count} files, freed {mb_freed} MB"
            )

        return removed_count
