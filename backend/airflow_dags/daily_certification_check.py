"""DAG: daily_certification_check
Queries the cert registry provider for every active vendor, raises
cert_expiry alerts at the 90/60/30-day thresholds. See Phase 2 spec §2.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task

from _common import run_monitoring_check


@dag(
    dag_id="daily_certification_check",
    description="Check vendor certification registries (SOC 2, ISO 27001) for expiring/expired certs",
    schedule="0 2 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
        "retry_exponential_backoff": True,
    },
    tags=["tprm", "monitoring"],
)
def daily_certification_check():
    @task
    def check_certifications() -> dict:
        from app.services.monitoring.monitoring_service import run_certification_check
        return run_monitoring_check(run_certification_check)

    check_certifications()


daily_certification_check()
