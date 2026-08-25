"""DAG: escalation_check
Sweeps for unacknowledged critical/high alerts past their SLA (Phase 2
spec §3/§4). Runs every 15 minutes — a 1-hour SLA is meaningless if it's
only checked once a day.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task

from _common import run_monitoring_check


@dag(
    dag_id="escalation_check",
    description="Escalate unacknowledged critical/high alerts past their SLA",
    schedule=timedelta(minutes=15),
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=2)},
    tags=["tprm", "monitoring"],
)
def escalation_check():
    @task
    def check_escalations() -> dict:
        from app.services.monitoring.alert_engine import run_escalation_check
        return run_monitoring_check(run_escalation_check, result_key="alerts_escalated")

    check_escalations()


escalation_check()
