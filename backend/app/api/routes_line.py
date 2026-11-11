from fastapi import APIRouter, Request, Header, HTTPException, BackgroundTasks
import json
from services.line_service import line_service
from database.connection import log_event

router = APIRouter(tags=["LINE Bot"])

@router.post("/api/line/webhook")
@router.post("/callback")
async def line_webhook(request: Request, background_tasks: BackgroundTasks, x_line_signature: str = Header(None)):
    body = await request.body()
    
    # 1. Verify Signature
    if x_line_signature:
        if not line_service.verify_signature(body, x_line_signature):
            await log_event("LINE", "WARNING", "Invalid signature received on LINE webhook")
            raise HTTPException(status_code=400, detail="Invalid signature")

    # 2. Parse payload
    try:
        data = json.loads(body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    events = data.get("events", [])
    for event in events:
        if event.get("type") == "message":
            msg_obj = event.get("message", {})
            if msg_obj.get("type") == "text":
                text = msg_obj.get("text", "")
                reply_token = event.get("replyToken")
                user_id = event.get("source", {}).get("userId", "")
                
                # Execute message handling
                background_tasks.add_task(
                    line_service.handle_message,
                    text,
                    user_id,
                    reply_token
                )

    return {"status": "ok"}
