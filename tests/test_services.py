import pytest
from pathlib import Path
from services.ai_service import AIService
from storage.manager import StorageManager

@pytest.mark.asyncio
async def test_ai_fallback_caption_structure():
    ai = AIService()
    res = ai._fallback_contextual_analysis(
        file_name="NOK_TAMRA_EP05_GREAT_MOLASSES_FLOOD_FINAL.mp4",
        frame_paths=[],
        duration=58.2
    )
    assert "caption_title" in res
    assert "caption_body" in res
    assert "hashtags" in res
    assert "#NOKTAMRA" in res["hashtags"]
    assert "analysis" in res
    assert "highlights" in res["analysis"]
    assert "target_audience" in res["analysis"]

def test_storage_manager_stats():
    mgr = StorageManager()
    stats = mgr.get_storage_stats()
    assert "used_total_mb" in stats
    assert "max_allowed_mb" in stats
    assert "percentage_used" in stats
