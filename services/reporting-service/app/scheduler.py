"""
Scheduled triggers for automated report generation, per the design doc's
"triggered by webhooks/schedulers" requirement. Each job opens its own DB
session (APScheduler jobs run outside FastAPI's request lifecycle, so they
can't use the `Depends(get_db)` pattern).
"""
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.database import SessionLocal
from app.report_generator import generate_and_send_report

logger = logging.getLogger("reporting.scheduler")

scheduler = BackgroundScheduler()


def _run_report_job(period_type: str):
    logger.info("Scheduled report job firing: %s", period_type)
    db = SessionLocal()
    try:
        generate_and_send_report(db, period_type, datetime.now(timezone.utc))
    except Exception:
        logger.exception("Scheduled report job failed: %s", period_type)
    finally:
        db.close()


def start_scheduler():
    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled via REPORTING_SCHEDULER_ENABLED=false")
        return

    scheduler.add_job(
        _run_report_job, CronTrigger.from_crontab(settings.daily_report_cron),
        args=["DAILY"], id="daily_report", replace_existing=True,
    )
    scheduler.add_job(
        _run_report_job, CronTrigger.from_crontab(settings.weekly_report_cron),
        args=["WEEKLY"], id="weekly_report", replace_existing=True,
    )
    scheduler.add_job(
        _run_report_job, CronTrigger.from_crontab(settings.monthly_report_cron),
        args=["MONTHLY"], id="monthly_report", replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler started: daily=%s weekly=%s monthly=%s",
        settings.daily_report_cron, settings.weekly_report_cron, settings.monthly_report_cron,
    )


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
