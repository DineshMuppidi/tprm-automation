# Technology Stack

Phase 0 deliverable. Each choice justified against: scalability, team
expertise (a single-developer/portfolio context — favor tools with strong
docs and low operational surprise), cost, and enterprise credibility (would
a Fortune 500 compliance/security team recognize and trust this stack?).

| Layer | Choice | Why this, not that |
|---|---|---|
| **Backend** | Python 3.11+, FastAPI | Async-native (matters for LLM calls and multi-source monitoring fan-out), OpenAPI schema generation for free (Phase 1 deliverable requires Swagger specs anyway), typing-first which pairs well with Pydantic models mirroring the Postgres schema. Chosen over Django: this platform is API-first with a separate React frontend, and doesn't need Django's batteries (admin site, templating) that would go unused. |
| **Database** | PostgreSQL 15+ | JSONB for the semi-structured bits (extracted LLM claims, contract terms, alert payloads) without giving up relational integrity for the parts that need it (findings, audit log, FKs). Enums map cleanly to the workflow state machines. Chosen over a NoSQL store: an audit-log-driven compliance platform needs transactional integrity and FK constraints more than it needs horizontal write scale it will never hit at Fortune-500-vendor-count row volumes (thousands, not billions). |
| **LLM** | Claude API, with a local Llama 3.2 fallback for air-gapped deployments | Claude for the primary path: strong structured-output reliability (JSON mode) for scoring/classification tasks and long-context handling for full contract/SOC-2-report analysis. Llama 3.2 fallback exists because the deployment target explicitly includes on-prem/air-gapped orgs (per project brief) where calling an external LLM API is a non-starter regardless of quality — the fallback trades some analysis quality for the ability to run at all. |
| **Orchestration** | Airflow | Purpose-built for exactly this shape of workload: independent, scheduled, retryable DAGs per data source (daily cert checks, hourly breach checks, weekly financial checks) with per-task retry/backoff and a visual run history that a compliance auditor can actually be shown. Chosen over cron+scripts: cron gives none of the retry semantics, dependency graph, or audit-friendly run history Phase 2 depends on. Chosen over a heavier stream-processing system (Kafka Streams, Flink): this is scheduled batch work, not high-throughput streaming — that would be over-engineering for the actual data volumes involved. |
| **Queue/cache** | Redis | Backs Airflow's queue depth signal, LLM-call backpressure buffering during Claude API degradation, and short-TTL caching of registry/API lookups (so a cert-registry scrape isn't repeated for every vendor on every DAG run). |
| **Frontend** | React 18 + TailwindCSS | Component reuse across the compliance dashboard and vendor portal (shared design system, different permission scopes). Tailwind keeps a solo-developer build visually consistent without hand-rolling a CSS architecture. Streamlit is used only for internal rapid-prototype views (e.g., a first-pass control-coverage heatmap) that never ship to vendors — it's the right tool for "show me the data fast," wrong tool for a permissioned multi-role production UI. |
| **Deployment** | Docker Compose for local/single-VM; Kubernetes manifests provided for orgs that need it | The brief's own deployment target is "on-premise Kali Linux VM or cloud-ready" — Docker Compose is what actually runs on a single VM without a K8s control plane to operate. Kubernetes manifests are still built (Phase 5) because a Fortune 500 evaluator will expect to see them, but they are not the default local dev path. |
| **Infra (cloud option)** | AWS: RDS (Postgres), S3 (evidence/contracts), CloudWatch, Secrets Manager, WAF/Shield | Chosen for enterprise familiarity (a hiring manager at a Fortune 500 shop is more likely to have AWS in-house than GCP/Azure for this kind of workload) and because RDS Multi-AZ + S3 versioning directly satisfy the RTO/backup requirements in Phase 5 without hand-rolling failover. |
| **CI/CD** | GitHub Actions | Zero additional infrastructure to operate (vs. self-hosted Jenkins), first-class Docker build/push and Terraform plan/apply actions, free tier sufficient for a portfolio-scale repo. |
| **IaC** | Terraform | Industry-default for AWS provisioning; declarative plan/apply review fits the "manual security review before prod deploy" gate in Phase 5. |

## Explicitly rejected alternatives

- **Django REST Framework** — more batteries than this API-first, no-admin-site
  architecture needs.
- **MongoDB** — the audit trail and remediation state machine are exactly
  the kind of invariant-heavy, relational data a document store makes
  harder to keep correct, not easier.
- **Self-hosted Jenkins** — an extra service to patch and operate for no
  capability GitHub Actions doesn't already provide at this scale.
- **Kafka/Flink for monitoring ingestion** — the actual throughput
  (scheduled polls against a few dozen external APIs) never approaches
  streaming-system territory; Airflow + Redis is simpler to operate and
  easier for a reviewer to reason about.
