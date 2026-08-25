# TPRM Automation Platform — System Architecture

Phase 0 deliverable. This document defines the system boundary, data flow,
scalability posture, and failure points for the platform described in
`README.md`. It is the foundation Phases 1–5 build against — application
code should not introduce a component that isn't represented here.

## 1. System Architecture

```mermaid
flowchart TB
    subgraph EXT["External — Internet"]
        VENDOR["Vendor user<br/>(browser)"]
        SOC2REG["SOC 2 Trust Search /<br/>ISO 27001 / FedRAMP registries"]
        HIBP["Have I Been Pwned"]
        SHODAN["Shodan / Censys"]
        NVD["NVD / GitHub Advisory / Rapid7"]
        NEWS["NewsAPI / RSS / X / Reddit"]
        FIN["D&B / Crunchbase / SEC EDGAR"]
        GMAIL["Gmail API<br/>(breach notif. parsing)"]
        CLAUDE["Claude API<br/>(LLM analysis)"]
    end

    subgraph EDGE["Edge — internal, internet-facing"]
        WAF["AWS WAF + Shield<br/>(DDoS)"]
        ALB["Load Balancer / API Gateway<br/>latency SLA: p99 &lt; 1s"]
    end

    subgraph APP["Application tier — internal, horizontally scalable"]
        WEBAPP["Web app (React)<br/>Compliance UI + Vendor Portal"]
        API["FastAPI backend<br/>REST, OpenAPI<br/>horizontal, stateless"]
        ASSESS["Assessment Engine<br/>(Phase 1)<br/>LLM scoring, questionnaire logic"]
        MONITOR["Monitoring Service<br/>(Phase 2)<br/>alert engine, impact assessment"]
        REMED["Remediation Engine<br/>(Phase 3)<br/>workflow state machine"]
        PLAYBOOK["Playbook Engine<br/>(Phase 4)<br/>contract mapping, control mapping"]
    end

    subgraph ASYNC["Async / scheduled tier — internal"]
        AIRFLOW["Airflow<br/>DAG scheduler<br/>vertical + worker autoscale"]
        REDIS["Redis<br/>queues + cache<br/>horizontal (cluster mode)"]
        WORKERS["Monitoring workers<br/>(one pool per data source)"]
    end

    subgraph DATA["Data tier — internal"]
        PG[("PostgreSQL 15+ (RDS)<br/>primary + read replica<br/>vertical, then read-replica horizontal")]
        S3[("S3<br/>contracts, certs, evidence<br/>horizontal, versioned + encrypted")]
    end

    subgraph OBS["Observability — internal"]
        CW["CloudWatch<br/>metrics, logs, alarms"]
    end

    VENDOR -->|HTTPS| WAF --> ALB --> WEBAPP
    WEBAPP --> API
    API --> ASSESS
    API --> REMED
    API --> PLAYBOOK
    ASSESS -->|LLM calls| CLAUDE
    REMED -->|evidence validation| CLAUDE
    ASSESS --> PG
    REMED --> PG
    PLAYBOOK --> PG
    API --> PG
    API --> S3
    ASSESS --> S3

    AIRFLOW --> WORKERS
    WORKERS --> SOC2REG
    WORKERS --> HIBP
    WORKERS --> SHODAN
    WORKERS --> NVD
    WORKERS --> NEWS
    WORKERS --> FIN
    WORKERS --> GMAIL
    WORKERS -->|write alerts| PG
    WORKERS <--> REDIS
    MONITOR --> REDIS
    MONITOR --> PG
    MONITOR -->|triggers| PLAYBOOK

    API --> CW
    AIRFLOW --> CW
    WORKERS --> CW

    style EXT fill:#2b2b2b,color:#fff
    style CLAUDE fill:#7a5cff,color:#fff
```

**Internal vs. external.** Everything inside `EDGE`, `APP`, `ASYNC`, `DATA`,
and `OBS` is internal infrastructure we operate. `EXT` is third-party —
we do not control its uptime, and every arrow crossing that boundary must
have a documented fallback (see §3, Integration Points).

**Scalability.**
| Component | Strategy | Notes |
|---|---|---|
| FastAPI backend | Horizontal | Stateless; scale by request volume behind ALB |
| Airflow scheduler | Vertical | Single scheduler is a bottleneck by design; workers scale horizontally |
| Monitoring workers | Horizontal (per source) | Each data source gets its own worker pool so a slow API (D&B) never blocks a fast one (NVD) |
| PostgreSQL | Vertical first, then read replicas | Writes stay single-primary for audit-log integrity; reporting queries hit replicas |
| Redis | Horizontal (cluster mode) | Queue depth is the early-warning signal for backpressure |
| S3 | Horizontal (inherent) | No action needed |

**Latency SLA.** API p99 < 1s (per Phase 5 monitoring target). Assessment
LLM scoring target < 5s per response (async, not on the request path —
vendor sees "analyzing..." and the UI polls/streams the result).

**Failover.** ALB health-checks the API tier and drains unhealthy nodes.
PostgreSQL uses RDS Multi-AZ automatic failover (target RTO 15 min, see
Phase 5 disaster recovery). Airflow DAGs use per-task retry with exponential
backoff (3 retries) rather than instance failover — a missed monitoring run
is recoverable, a stuck one isn't.

**Failure points worth naming explicitly:**
1. **Claude API outage** — assessment scoring and evidence validation both
   depend on it. Mitigation: queue requests in Redis, retry with backoff;
   surface "pending analysis" state in the UI rather than blocking vendor
   submission. Air-gapped deployments fall back to a local Llama 3.2
   instance with a reduced prompt set (see Tech Stack doc, §LLM).
2. **A single monitoring source going down** (e.g., HIBP) — must not stop
   the other DAGs. Each source has its own DAG, its own retry policy, and
   its own row in `monitoring_sources` with health status shown on the
   dashboard (Phase 2, Monitoring Status Page).
3. **Airflow scheduler itself down** — no new DAG runs fire, but the API
   and existing data are unaffected; this is a "stale monitoring data"
   degradation, not an outage, and is what Runbook 3 (Phase 5) exists for.
4. **PostgreSQL primary down** — the whole write path stops; this is the
   only true single point of failure in the design, which is why it gets
   Multi-AZ failover and the tightest RTO in the platform.

## 2. Data Model

See [`backend/db/schema/schema.sql`](../../backend/db/schema/schema.sql) —
executable, PostgreSQL 15+, validated against a live Postgres 18 instance
during Phase 0. Covers: vendor profiles, questionnaire templates/assessments,
findings/remediation, contracts/obligations, framework/control mapping,
monitoring alerts, and an append-only audit log (enforced by trigger, not
just convention).

## 3. Integration Points

See [`integrations.md`](integrations.md).

## 4. Threat Model

See [`threat-model.md`](threat-model.md).

## 5. Real-World Scenario Walkthrough

See [`scenario-vendor-ransomware.md`](scenario-vendor-ransomware.md).

## 6. Technology Stack

See [`tech-stack.md`](tech-stack.md).
