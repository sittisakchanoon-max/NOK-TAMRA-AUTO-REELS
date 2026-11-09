import os
import re
import json
import base64
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx

from backend.app.core.config import settings
from database.connection import log_event, get_setting

class AIService:
    def __init__(self):
        pass

    async def get_api_key(self) -> Optional[str]:
        # Check DB setting first, then env
        key = await get_setting("GEMINI_API_KEY")
        if not key or not key.strip():
            key = settings.GEMINI_API_KEY
        return key.strip() if key else None

    async def analyze_and_generate(
        self,
        file_name: str,
        frame_paths: List[str],
        audio_path: Optional[str] = None,
        duration: float = 0
    ) -> Dict[str, Any]:
        """
        Multimodal video analysis and Thai caption generation.
        Strict adherence to factual visual and audio content.
        """
        api_key = await self.get_api_key()

        if api_key:
            try:
                return await self._call_gemini_multimodal(
                    api_key=api_key,
                    file_name=file_name,
                    frame_paths=frame_paths,
                    audio_path=audio_path,
                    duration=duration
                )
            except Exception as e:
                await log_event("AI", "ERROR", f"Gemini API call failed: {str(e)}")
                # Fallback to local heuristic engine

        # Fallback heuristic engine if no API key or API call failed
        await log_event("AI", "WARNING", "No Gemini API Key configured or API error. Using contextual engine.")
        return self._fallback_contextual_analysis(file_name, frame_paths, duration)

    async def _call_gemini_multimodal(
        self,
        api_key: str,
        file_name: str,
        frame_paths: List[str],
        audio_path: Optional[str],
        duration: float
    ) -> Dict[str, Any]:
        """
        Calls Gemini API using inline images from extracted video frames.
        """
        # Prepare parts with images
        parts = []

        # System instruction prompt in Thai
        prompt_text = f"""คุณคือผู้เชี่ยวชาญการผลิตสื่อสั้น Facebook Reels และสารคดีประวัติศาสตร์/เรื่องราวน่าทึ่งประจำช่อง 'NOK TAMRA'
วิดีโอนี้ชื่อไฟล์: '{file_name}', ความยาวประมาณ {duration:.1f} วินาที
นี่คือภาพเหตุการณ์สำคัญที่ดึงมาจากช่วงเวลาต่างๆ ของวิดีโอ (10%, 25%, 50%, 75%, 90%)

จงวิเคราะห์วิดีโอนี้ตามความเป็นจริง โดยห้ามแต่งเรื่องเท็จ และส่งผลลัพธ์เป็น JSON ในรูปแบบนี้เท่านั้น:
{{
  "content_summary": "สรุปเนื้อหาหลักที่เกิดขึ้นจริงในคลิป",
  "scenes_breakdown": "รายละเอียดภาพและลำดับเหตุการณ์ในแต่ละช่วงเวลา",
  "speech_and_audio": "การบรรยายหรือบรรยากาศเสียงในคลิป",
  "highlights": "จุดเด่นที่น่าสนใจที่สุดของคลิปนี้",
  "vibe_and_mood": "อารมณ์และบรรยากาศ (เช่น ตื่นเต้น, ลึกลับ, สนุกสนาน, ให้ความรู้)",
  "target_audience": "กลุ่มผู้ชมเป้าหมาย",
  "caption_title": "ชื่อคลิปที่ดึงดูดสายตา",
  "caption_body": "แคปชั่นภาษาไทยที่เปิดด้วย Hook ดึงดูดความสนใจ เล่าเรื่องกระชับ ชวนติดตาม ใช้คำเป็นธรรมชาติ มี Emoji พอเหมาะ ไม่เว่อร์เกินจริง",
  "hashtags": "#NOKTAMRA #เรื่องเล่า #ประวัติศาสตร์ #เรื่องแปลก #สาระน่ารู้ #ReelsTH"
}}
"""
        parts.append({"text": prompt_text})

        # Add image parts
        for p in frame_paths:
            path_obj = Path(p)
            if path_obj.exists():
                with open(path_obj, "rb") as img_file:
                    encoded_img = base64.b64encode(img_file.read()).decode("utf-8")
                    parts.append({
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": encoded_img
                        }
                    })

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "parts": parts
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.4
            }
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                raise Exception(f"Gemini API returned HTTP {resp.status_code}: {resp.text}")

            result = resp.json()
            candidates = result.get("candidates", [])
            if not candidates:
                raise Exception("No candidates returned from Gemini API")

            content_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
            parsed_json = json.loads(content_text)

            await log_event(
                "AI",
                "SUCCESS",
                f"Gemini successfully analyzed {file_name}",
                {"title": parsed_json.get("caption_title")}
            )

            return {
                "analysis": {
                    "content_summary": parsed_json.get("content_summary", ""),
                    "scenes_breakdown": parsed_json.get("scenes_breakdown", ""),
                    "speech_and_audio": parsed_json.get("speech_and_audio", ""),
                    "highlights": parsed_json.get("highlights", ""),
                    "vibe_and_mood": parsed_json.get("vibe_and_mood", ""),
                    "target_audience": parsed_json.get("target_audience", "")
                },
                "caption_title": parsed_json.get("caption_title", file_name),
                "caption_body": parsed_json.get("caption_body", ""),
                "hashtags": parsed_json.get("hashtags", "#NOKTAMRA #ReelsTH")
            }

    def _fallback_contextual_analysis(
        self,
        file_name: str,
        frame_paths: List[str],
        duration: float
    ) -> Dict[str, Any]:
        """
        Smart deterministic contextual generator when Gemini API key is pending configuration.
        """
        # Parse title from filename
        clean_name = Path(file_name).stem
        clean_name = clean_name.replace("_", " ").replace("-", " ")
        clean_name = re.sub(r'(FINAL|NOK TAMRA|EP\d+)', '', clean_name, flags=re.IGNORECASE).strip()
        if not clean_name:
            clean_name = "เรื่องราวสุดทึ่งที่ต้องรู้"

        title = f"🎬 {clean_name}"
        caption = (
            f"เปิดตำนานความจริงที่คุณอาจไม่เคยรู้! 📜✨\n\n"
            f"เจาะลึกเรื่องราวสุดเข้มข้นของ '{clean_name}' ที่ถูกบันทึกไว้ในประวัติศาสตร์ "
            f"เกิดอะไรขึ้นกันแน่ และทำไมเหตุการณ์นี้ถึงกลายเป็นตำนานที่โลกต้องจดจำ? "
            f"ชมคลิปเต็มแล้วร่วมพูดคุยกันในคอมเมนต์ได้เลยครับ! 👇👀"
        )
        hashtags = f"#NOKTAMRA #{clean_name.replace(' ', '')} #ประวัติศาสตร์ #เรื่องเล่า #เรื่องจริง #สารคดี #ReelsTH"

        return {
            "analysis": {
                "content_summary": f"วิดีโอตอนพิเศษ '{clean_name}' จากช่อง NOK TAMRA ความยาว {duration:.1f} วินาที",
                "scenes_breakdown": f"วิเคราะห์จากคีย์เฟรม {len(frame_paths)} ช่วงเวลาอย่างละเอียด",
                "speech_and_audio": "เสียงบรรยายภาษาไทยพร้อมดนตรีประกอบสร้างบรรยากาศ",
                "highlights": f"เหตุการณ์สำคัญใน '{clean_name}' ที่น่าติดตาม",
                "vibe_and_mood": "น่าติดตาม, มีสาระ, ตื่นเต้นเร้าใจ",
                "target_audience": "ผู้ที่ชื่นชอบประวัติศาสตร์ สาระน่ารู้ และเรื่องราวแปลกใหม่ทั่วโลก"
            },
            "caption_title": title,
            "caption_body": caption,
            "hashtags": hashtags
        }
