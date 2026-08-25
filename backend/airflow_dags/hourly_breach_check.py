"""DAG: hourly_breach_check
Breach databases + CVE/vulnerability feeds for every active vendor.
High priority, aggressive retries — per Phase 2 spec §2: "if a vendor was
breached, we need to know NOW." A critical breach signal also triggers the
incident impact assessment and auto-creates a finding (see
app/services/monitoring/impact_assessor.py) — that happens inside
run_breach_check itself, not as a separate DAG task, so it can't run
without the alert that triggered it.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task

from _common import run_monitoring_check


@dag(
    dag_id="hourly_breach_check",
    description="Check breach databases and CVE/vulnerability feeds for every active vendor",
    schedule="0 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={
        "retries": 5,
        "retry_delay": timedelta(minutes=1),
        "retry_exponential_backoff": True,
    },
    tags=["tprm", "monitoring", "high-priority"],
)
def hourly_breach_check():
    @task
    def check_breaches_and_cves() -> dict:
        from app.services.monitoring.monitoring_service import run_breach_check
        return run_monitoring_check(run_breach_check)

    check_breaches_and_cves()


hourly_breach_check()
