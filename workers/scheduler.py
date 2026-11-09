import datetime
import asyncio
from typing import Optional, Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.app.core.config import settings
from database.connection import log_event, get_setting
from workers.pipeline_worker import PipelineWorker

class AutomationScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.worker = PipelineWorker()
        self.last_run: Optional[datetime.datetime] = None
        self.next_run: Optional[datetime.datetime] = None
        self.job_id = "nok_tamra_pipeline_job"

    async def start(self):
        """
        Starts the background scheduler.
        """
        interval_min_str = await get_setting("GDRIVE_CHECK_INTERVAL_MINUTES")
        interval_min = int(interval_min_str) if interval_min_str and interval_min_str.isdigit() else settings.GDRIVE_CHECK_INTERVAL_MINUTES

        self.scheduler.add_job(
            self._scheduled_task,
            trigger=IntervalTrigger(minutes=interval_min),
            id=self.job_id,
            replace_existing=True,
            next_run_time=datetime.datetime.now() # trigger initial check on start
        )
        self.scheduler.start()
        self.update_next_run()
        await log_event("SCHEDULER", "INFO", f"Scheduler started with {interval_min} minutes interval.")

    def update_next_run(self):
        job = self.scheduler.get_job(self.job_id)
        if job and job.next_run_time:
            self.next_run = job.next_run_time

    async def _scheduled_task(self):
        self.last_run = datetime.datetime.now()
        await self.worker.run_pipeline_cycle()
        self.update_next_run()

    async def trigger_now(self) -> Dict[str, Any]:
        """
        Manual on-demand trigger called from the iPhone dashboard.
        """
        self.last_run = datetime.datetime.now()
        await log_event("SCHEDULER", "INFO", "Manual scan triggered from Dashboard")
        res = await self.worker.run_pipeline_cycle()
        self.update_next_run()
        return res

    async def update_interval(self, minutes: int):
        job = self.scheduler.get_job(self.job_id)
        if job:
            job.reschedule(trigger=IntervalTrigger(minutes=minutes))
            self.update_next_run()
            await log_event("SCHEDULER", "INFO", f"Scheduler interval changed to {minutes} minutes")

    def get_status(self) -> Dict[str, Any]:
        self.update_next_run()
        return {
            "is_running": self.scheduler.running,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "is_processing": self.worker._is_running
        }

scheduler_instance = AutomationScheduler()
