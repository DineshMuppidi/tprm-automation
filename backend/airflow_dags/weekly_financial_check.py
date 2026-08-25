"""DAG: weekly_financial_check
Weekly cadence deliberately — financial distress signals move slowly
compared to breaches, and (per Phase 2 spec §2) a paid API like D&B is the
expensive one in this pipeline, so retries are capped rather than
aggressive.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task

from _common import run_monitoring_check


@dag(
    dag_id="weekly_financial_check",
    description="Check financial distress signals (credit rating, SEC filings) for every active vendor",
    schedule="0 3 * * 1",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=30),
    },
    tags=["tprm", "monitoring"],
)
def weekly_financial_check():
    @task
    def check_financials() -> dict:
        from app.services.monitoring.monitoring_service import run_financial_check
        return run_monitoring_check(run_financial_check)

    check_financials()


weekly_financial_check()
