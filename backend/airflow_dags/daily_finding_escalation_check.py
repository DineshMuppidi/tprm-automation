"""DAG: daily_finding_escalation_check
Finding SLAs are day-granularity (3-day ack grace, 30/60/90/120-day
deadlines, 14-day legal escalation threshold) — daily is the right cadence,
unlike the alert engine's escalation_check (minute-granularity SLAs, runs
every 15 minutes). See Phase 3 spec §4 and
app/services/remediation/escalation_engine.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task

from _common import run_monitoring_check


@dag(
    dag_id="daily_finding_escalation_check",
    description="Remind on unacknowledged findings, mark overdue findings, escalate severely-overdue ones to Legal, flag repeated rejections",
    schedule="0 7 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=15)},
    tags=["tprm", "remediation"],
)
def daily_finding_escalation_check():
    @task
    def check_finding_escalations() -> dict:
        from app.services.remediation.escalation_engine import run_finding_escalation_check
        return run_monitoring_check(run_finding_escalation_check, result_key="summary")

    check_finding_escalations()


daily_finding_escalation_check()
