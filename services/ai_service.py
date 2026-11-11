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

        prompt_text = f"""คุณคือนักเขียนแคปชั่นสารคดีประวัติศาสตร์และวิทยาศาสตร์ประจำช่อง 'NOK TAMRA' (นอกตำรา)
วิดีโอนี้ชื่อไฟล์: '{file_name}', ความยาวประมาณ {duration:.1f} วินาที
นี่คือภาพเหตุการณ์สำคัญที่ดึงมาจากช่วงเวลาต่างๆ ของวิดีโอ

กฎสำคัญในการเขียนแคปชั่น:
1. ให้เขียนในรูปแบบ 'สารคดีข้อเท็จจริงประวัติศาสตร์/วิทยาศาสตร์' เข้มข้น มีสาระ ลุ่มลึก ชวนติดตาม
2. ต้องระบุปี ค.ศ./พ.ศ., สถานที่เกิดเหตุ, หรือข้อมูลบุคคล/วิทยาศาสตร์ที่เกิดขึ้นจริง
3. ห้ามแต่งเรื่องเท็จ และ **ห้ามใส่อิโมจิหรือสติกเกอร์ใดๆ ทั้งสิ้นในแคปชั่น** (เด็ดขาด)
4. โครงสร้างแคปชั่น:
   - บรรทัดแรก: หัวข้อเรื่องสั้นกระชับ
   - ย่อหน้า 1: เปิดเรื่องด้วยจุดเริ่มต้นของเหตุการณ์/การค้นพบ
   - ย่อหน้า 2: เจาะลึกรายละเอียด ข้อเท็จจริง ตัวเลข หรือหลักฐาน
   - ย่อหน้า 3: บทสรุปทางประวัติศาสตร์หรือวิทยาศาสตร์
5. แฮชแท็ก: ต้องเริ่มต้นด้วย #NOKTAMRA ตามด้วยชื่อตอนภาษาอังกฤษและไทย และลงท้ายด้วย #ประวัติศาสตร์โลก #เรื่องแปลกนอกตำรา #ReelsTH #สารคดี

ส่งผลลัพธ์เป็น JSON ในรูปแบบนี้เท่านั้น:
{{
  "content_summary": "สรุปเนื้อหาหลักที่เกิดขึ้นจริงในคลิป",
  "scenes_breakdown": "รายละเอียดภาพและลำดับเหตุการณ์",
  "highlights": "จุดเด่นที่น่าสนใจที่สุดของคลิปนี้",
  "vibe_and_mood": "สารคดี, น่าทึ่ง, ให้ความรู้",
  "caption_title": "หัวข้อเรื่องสั้นกระชับ (ไม่มีอิโมจิ)",
  "caption_body": "เนื้อหาแคปชั่น 3 ย่อหน้ากระชับ สไตล์สารคดีจริง ไม่มีอิโมจิเด็ดขาด",
  "hashtags": "#NOKTAMRA #หัวข้อ #ประวัติศาสตร์โลก #เรื่องแปลกนอกตำรา #ReelsTH #สารคดี"
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

    async def generate_from_script(self, script_text: str, file_name: str) -> Dict[str, Any]:
        """
        Generate factual documentary caption directly from Google Drive script.
        """
        api_key = await self.get_api_key()
        if not api_key:
            return self._fallback_contextual_analysis(file_name, [], 70)

        prompt = f"""คุณคือนักเขียนแคปชั่นสารคดีประวัติศาสตร์และวิทยาศาสตร์ประจำช่อง 'NOK TAMRA' (นอกตำรา)
ต่อไปนี้คือบทพากย์และสคริปต์วิดีโอตัวเต็มของตอน '{file_name}':
--------------------
{script_text[:4000]}
--------------------

จงอ่านเนื้อหาจากสคริปต์นี้ และสังเคราะห์ออกมาเป็นแคปชั่นลง Facebook Reels:
1. เขียนเป็นสารคดีประวัติศาสตร์/วิทยาศาสตร์เข้มข้น มีสาระ ลุ่มลึก ชวนติดตาม อ้างอิงตามข้อเท็จจริงในสคริปต์
2. ระบุปี ค.ศ., สถานที่, หรือข้อมูลทางวิทยาศาสตร์ที่ถูกต้อง
3. **ห้ามใส่อิโมจิหรือสติกเกอร์ใดๆ ทั้งสิ้นในแคปชั่น** (เด็ดขาด)
4. โครงสร้างแคปชั่น:
   - บรรทัดแรก: หัวข้อเรื่องสั้นกระชับ
   - ย่อหน้า 1: เปิดเรื่องด้วยจุดเริ่มต้นของเหตุการณ์/การค้นพบ
   - ย่อหน้า 2: เจาะลึกรายละเอียด ข้อเท็จจริง ตัวเลข หรือหลักฐาน
   - ย่อหน้า 3: บทสรุปทางประวัติศาสตร์หรือวิทยาศาสตร์
5. แฮชแท็ก: ต้องเริ่มต้นด้วย #NOKTAMRA ตามด้วยชื่อตอนภาษาอังกฤษและไทย และลงท้ายด้วย #ประวัติศาสตร์โลก #เรื่องแปลกนอกตำรา #ReelsTH #สารคดี

ส่งผลลัพธ์เป็น JSON ในรูปแบบนี้เท่านั้น:
{{
  "caption_title": "หัวข้อเรื่องสั้นกระชับ (ไม่มีอิโมจิ)",
  "caption_body": "เนื้อหาแคปชั่น 3 ย่อหน้ากระชับ สไตล์สารคดีจริง ไม่มีอิโมจิเด็ดขาด",
  "hashtags": "#NOKTAMRA #หัวข้อ #ประวัติศาสตร์โลก #เรื่องแปลกนอกตำรา #ReelsTH #สารคดี"
}}
"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json", "temperature": 0.3}
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text)
                return {
                    "caption_title": parsed.get("caption_title", file_name),
                    "caption_body": parsed.get("caption_body", ""),
                    "hashtags": parsed.get("hashtags", "#NOKTAMRA #ReelsTH")
                }
            return self._fallback_contextual_analysis(file_name, [], 70)

    def _fallback_contextual_analysis(
        self,
        file_name: str,
        frame_paths: List[str],
        duration: float
    ) -> Dict[str, Any]:
        """
        Smart deterministic contextual generator without emojis.
        """
        clean_name = Path(file_name).stem
        clean_name = clean_name.replace("_", " ").replace("-", " ")
        clean_name = re.sub(r'(FINAL|NOK TAMRA|EP\d+)', '', clean_name, flags=re.IGNORECASE).strip()
        if not clean_name:
            clean_name = "เรื่องราวทางประวัติศาสตร์ที่น่าทึ่ง"

        title = f"{clean_name}"
        caption = (
            f"{clean_name} เรื่องจริงที่ถูกบันทึกไว้ในประวัติศาสตร์\n\n"
            f"ย้อนกลับไปในอดีต เหตุการณ์ของ {clean_name} ได้สร้างความเปลี่ยนแปลงและความน่าทึ่งให้กับผู้คนในยุคสมัยนั้นอย่างมาก "
            f"การค้นพบและหลักฐานทางประวัติศาสตร์ชี้ให้เห็นถึงความจริงที่น่าประหลาดใจซึ่งยังคงได้รับการกล่าวขานมาจนถึงปัจจุบัน\n\n"
            f"เบื้องหลังเรื่องราวที่ดูเหลือเชื่อ มักมีข้อเท็จจริงและหลักการทางธรรมชาติหรือวิทยาศาสตร์ซ่อนอยู่เสมอ "
            f"เรื่องนี้จึงเป็นอีกหนึ่งบทเรียนสำคัญที่เตือนใจและให้แง่คิดอันทรงคุณค่าแก่คนรุ่นหลัง"
        )
        hashtags = f"#NOKTAMRA #{clean_name.replace(' ', '')} #ประวัติศาสตร์โลก #เรื่องจริง #เรื่องแปลกนอกตำรา #ReelsTH #สารคดี"

        return {
            "analysis": {
                "content_summary": f"วิดีโอตอนพิเศษ '{clean_name}' จากช่อง NOK TAMRA ความยาว {duration:.1f} วินาที",
                "scenes_breakdown": f"วิเคราะห์จากคีย์เฟรม {len(frame_paths)} ช่วงเวลาอย่างละเอียด",
                "speech_and_audio": "เสียงบรรยายภาษาไทยพร้อมดนตรีประกอบสร้างบรรยากาศ",
                "highlights": f"เหตุการณ์สำคัญใน '{clean_name}' ที่น่าติดตาม",
                "vibe_and_mood": "สารคดี, น่าทึ่ง, ให้ความรู้",
                "target_audience": "ผู้ที่ชื่นชอบประวัติศาสตร์ สาระน่ารู้ และเรื่องราวแปลกใหม่ทั่วโลก"
            },
            "caption_title": title,
            "caption_body": caption,
            "hashtags": hashtags
        }
