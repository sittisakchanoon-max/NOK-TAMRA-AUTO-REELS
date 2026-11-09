from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, delete

from database.connection import get_db
from database.models import SystemLog

router = APIRouter(prefix="/api/logs", tags=["Logs"])

@router.get("")
async def get_system_logs(
    category: Optional[str] = Query(None, description="Category filter (e.g. DRIVE, AI, FACEBOOK, WORKER, SYSTEM)"),
    level: Optional[str] = Query(None, description="Level filter (e.g. INFO, SUCCESS, WARNING, ERROR)"),
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(SystemLog).order_by(desc(SystemLog.created_at))
    if category and category.upper() != "ALL":
        stmt = stmt.where(SystemLog.category == category.upper())
    if level and level.upper() != "ALL":
        stmt = stmt.where(SystemLog.level == level.upper())
    stmt = stmt.limit(limit)

    res = await db.execute(stmt)
    records = res.scalars().all()

    return [
        {
            "id": r.id,
            "category": r.category,
            "level": r.level,
            "message": r.message,
            "details": r.details,
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in records
    ]

@router.delete("")
async def clear_logs(db: AsyncSession = Depends(get_db)):
    await db.execute(delete(SystemLog))
    await db.commit()
    return {"success": True, "message": "All logs cleared"}
