"""DAG: daily_news_monitoring
Runs twice daily. Only negative/material stories become alerts — sentiment
classification happens inside the provider (mock: pre-scripted; live:
app/services/monitoring/news_classifier.py) before this ever touches the
alert engine, per Phase 2 spec §2 task ordering (search -> classify ->
route only if material).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task

from _common import run_monitoring_check


@dag(
    dag_id="daily_news_monitoring",
    description="Search news/reputation sources for material vendor mentions",
    schedule="0 8,20 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=10),
    },
    tags=["tprm", "monitoring"],
)
def daily_news_monitoring():
    @task
    def check_news() -> dict:
        from app.services.monitoring.monitoring_service import run_news_check
        return run_monitoring_check(run_news_check)

    check_news()


daily_news_monitoring()
