import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from backend.app.core.config import settings
from database.connection import log_event

class VideoService:
    def __init__(self):
        self.thumbnails_dir = settings.THUMBNAILS_DIR

    async def get_metadata(self, video_path: str) -> Dict[str, Any]:
        """
        Extract duration, resolution, audio streams using ffprobe.
        """
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            video_path
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                await log_event("SYSTEM", "ERROR", f"ffprobe error: {stderr.decode()}")
                return {"duration": 0, "width": 0, "height": 0, "has_audio": False}

            data = json.loads(stdout.decode())
            format_info = data.get("format", {})
            duration = float(format_info.get("duration", 0))

            width = 0
            height = 0
            has_audio = False

            for stream in data.get("streams", []):
                codec_type = stream.get("codec_type")
                if codec_type == "video" and width == 0:
                    width = int(stream.get("width", 0))
                    height = int(stream.get("height", 0))
                elif codec_type == "audio":
                    has_audio = True

            return {
                "duration": duration,
                "width": width,
                "height": height,
                "resolution": f"{width}x{height}",
                "has_audio": has_audio
            }
        except Exception as e:
            await log_event("SYSTEM", "ERROR", f"Exception getting video metadata: {str(e)}")
            return {"duration": 0, "width": 0, "height": 0, "has_audio": False}

    async def extract_thumbnail(self, video_path: str, video_id: str) -> Optional[str]:
        """
        Extract an attractive thumbnail from around 10%-20% into the video.
        """
        meta = await self.get_metadata(video_path)
        duration = meta.get("duration", 10.0)
        timestamp = max(1.0, min(5.0, duration * 0.15))

        thumb_name = f"thumb_{video_id}.jpg"
        out_path = self.thumbnails_dir / thumb_name

        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(timestamp),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            "-vf", "scale=640:-1",
            str(out_path)
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            if out_path.exists() and out_path.stat().st_size > 0:
                return f"/api/videos/{video_id}/thumbnail"
            return None
        except Exception as e:
            await log_event("SYSTEM", "ERROR", f"Failed to extract thumbnail: {e}")
            return None

    async def extract_multi_frames(self, video_path: str, video_id: str, count: int = 5) -> List[str]:
        """
        Extract keyframes across multiple timestamps (e.g. 10%, 25%, 50%, 75%, 90%)
        for deep multi-stage AI visual analysis.
        """
        meta = await self.get_metadata(video_path)
        duration = meta.get("duration", 10.0)
        if duration <= 0:
            duration = 10.0

        ratios = [0.10, 0.25, 0.50, 0.75, 0.90][:count]
        frame_paths = []

        frames_dir = settings.STORAGE_DIR / "frames" / video_id
        frames_dir.mkdir(parents=True, exist_ok=True)

        for i, ratio in enumerate(ratios):
            time_pos = round(duration * ratio, 2)
            frame_path = frames_dir / f"frame_{i}_{int(time_pos)}s.jpg"
            cmd = [
                "ffmpeg",
                "-y",
                "-ss", str(time_pos),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "3",
                "-vf", "scale=800:-1",
                str(frame_path)
            ]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()
                if frame_path.exists() and frame_path.stat().st_size > 0:
                    frame_paths.append(str(frame_path))
            except Exception as e:
                print(f"Error extracting frame at {time_pos}s: {e}")

        return frame_paths

    async def extract_audio(self, video_path: str, video_id: str) -> Optional[str]:
        """
        Extract audio track to 16kHz mono MP3 for speech-to-text.
        """
        audio_dir = settings.STORAGE_DIR / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        audio_path = audio_dir / f"{video_id}.mp3"

        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "libmp3lame",
            "-ac", "1",
            "-ar", "16000",
            "-b:a", "64k",
            str(audio_path)
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            if audio_path.exists() and audio_path.stat().st_size > 0:
                return str(audio_path)
            return None
        except Exception as e:
            await log_event("SYSTEM", "ERROR", f"Audio extraction failed: {e}")
            return None
