# Kubernetes Manifests

Phase 5 deliverable. Real, valid manifests for the deployment target the
Phase 0 architecture doc describes for orgs beyond a single-VM deployment
(see `docker-compose.yml` for the single-VM path).

**Not applied to a real cluster.** `kubectl` isn't installed in this
sandbox, and there's no cluster to point it at — same honesty as
`backend/airflow_dags/` and the CI/CD workflows: written correctly against
the schemas these API versions actually expect, not run.

## Apply order

```bash
kubectl apply -f 00-namespace.yaml
kubectl create secret generic tprm-secrets -n tprm --from-env-file=backend/.env   # NOT from 02-secret.example.yaml directly
kubectl apply -f 01-configmap.yaml
kubectl apply -f 10-backend.yaml
kubectl apply -f 11-frontend.yaml
kubectl apply -f 20-ingress.yaml
```

`02-secret.example.yaml` documents which keys `tprm-secrets` needs — don't
apply it directly with real values filled in; that puts secrets in git
history. Use `kubectl create secret ... --from-env-file` from a `.env`
that's never committed, or better, a real secrets manager integration
(External Secrets Operator + AWS Secrets Manager, matching the Phase 0
architecture doc's AWS choices).

## What's deliberately not here

- **Database.** `DATABASE_URL` in the secret points at wherever Postgres
  actually runs — RDS in the Phase 0 architecture, not a StatefulSet in
  this namespace. Running Postgres in-cluster is a legitimate choice for
  some orgs but isn't what the architecture doc specifies, so it's not
  templated here.
- **Redis, Airflow.** Same reasoning — the Phase 0 architecture names
  these as separate services with their own operational needs (Airflow
  especially: its own metadata DB, scheduler, and in 3.x an API server).
  Adding half-configured manifests for services that were never actually
  stood up anywhere would be worse than not including them.
- **NetworkPolicies, PodDisruptionBudgets.** Real production hardening
  that depends on the specific CNI/cluster in use — noted as a gap here
  rather than guessed at generically.
