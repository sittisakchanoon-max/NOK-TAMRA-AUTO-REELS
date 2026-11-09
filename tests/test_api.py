import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from database.connection import init_db

@pytest.mark.asyncio
async def test_dashboard_endpoints():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Test stats
        res = await ac.get("/api/dashboard/stats")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ONLINE"
        assert "metrics" in data
        assert "scheduler" in data
        assert "google_drive" in data

@pytest.mark.asyncio
async def test_settings_endpoints():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/settings")
        assert res.status_code == 200
        data = res.json()
        assert "gdrive_folder_id" in data

        # Test update
        post_res = await ac.post("/api/settings", json={
            "gdrive_check_interval_minutes": 20
        })
        assert post_res.status_code == 200
        assert post_res.json()["success"] is True

@pytest.mark.asyncio
async def test_videos_endpoints():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/videos")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

@pytest.mark.asyncio
async def test_logs_endpoints():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/logs")
        assert res.status_code == 200
        assert isinstance(res.json(), list)
