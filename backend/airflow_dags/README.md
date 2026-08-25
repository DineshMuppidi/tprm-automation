# Airflow DAGs — Phase 2 Monitoring Orchestration

These are real Airflow 3.x DAG definitions (TaskFlow API) implementing the
schedule the Phase 2 spec calls for: `daily_certification_check`,
`hourly_breach_check`, `daily_news_monitoring`, `weekly_financial_check`,
plus `escalation_check` for the alert-SLA escalation sweep.

**Not executed in this environment.** Apache Airflow wasn't installed or
run here — it needs its own metadata database, scheduler, and (in Airflow
3.x) API server/DAG processor, which is real infrastructure to stand up
and doesn't fit a sandboxed dev container with no Docker and no root.
Rather than fake a screenshot of a scheduler that never ran, these DAGs
are thin, honest wrappers: every DAG task calls straight into
`app/services/monitoring/monitoring_service.py`, and *that* code is what's
actually tested — via `backend/tests/test_monitoring.py` (unit +
live-Postgres integration) and by hand against a real Postgres instance
(see the Phase 2 commit message / project README for what was verified).
Point Airflow's `dags_folder` at this directory and these run as-is; the
business logic underneath doesn't change whether Airflow is present.

## Deploying for real

```bash
pip install apache-airflow==3.3.1
export AIRFLOW_HOME=~/airflow
airflow db migrate
airflow standalone   # or: scheduler + api-server as separate processes
```

Point `[core] dags_folder` (in `airflow.cfg`) at this directory, and make
sure Airflow's Python environment has `backend/` on `PYTHONPATH` and a
`.env` (or equivalent Airflow Connection/Variable) providing `DATABASE_URL`
— these DAGs import `app.db` and `app.services.monitoring.*` directly.

## Schedule (matches Phase 2 spec §2)

| DAG | Schedule | Priority |
|---|---|---|
| `daily_certification_check` | `0 2 * * *` (2 AM UTC) | Normal |
| `hourly_breach_check` | `0 * * * *` (hourly) | High — aggressive retry |
| `daily_news_monitoring` | `0 8,20 * * *` (twice daily) | Normal |
| `weekly_financial_check` | `0 3 * * 1` (Monday 3 AM UTC) | Normal — paid APIs, costs money to over-run |
| `escalation_check` | `*/15 * * * *` (every 15 min) | Needs tight cadence — a 1-hour SLA is meaningless if checked once a day |
