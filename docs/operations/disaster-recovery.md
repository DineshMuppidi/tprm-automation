# Disaster Recovery & Business Continuity

Phase 5 deliverable. RTO/RPO targets, backup strategy, and disaster
scenarios — including a backup/restore cycle that was **actually run**
against a live PostgreSQL 18 instance during development, not just
described.

## Recovery targets

| Scenario | RTO | RPO |
|---|---|---|
| App tier down (pod/instance crash) | < 5 min | 0 (stateless, k8s HPA/liveness restarts automatically) |
| Database unreachable, recoverable in place | < 15 min | < 5 min (RDS Multi-AZ failover, production only — see `terraform/main.tf`'s `multi_az = var.environment == "production"`) |
| Database corrupted, restore from backup | < 4 hours | < 24 hours on daily snapshots; < 5 min with point-in-time recovery enabled |
| Full region outage | Not currently designed for | — a genuine gap; the Phase 0 architecture doc names this as a stretch goal, not a committed target, and nothing in this build implements cross-region failover |

These match the Phase 0 architecture doc's original targets — Phase 5
didn't revise them, just built the backup mechanism that makes the
"restore from backup" row achievable rather than aspirational.

## Backup strategy

- **Production (Terraform)**: RDS automated backups, `backup_retention_
  period = 30` days for `production` / `7` for `staging`
  (`terraform/main.tf`), point-in-time recovery enabled by default on RDS.
  S3 evidence bucket is versioned (`aws_s3_bucket_versioning`) — an
  accidental overwrite/delete is recoverable without a full DB restore.
- **Manual/scripted backup**: `backend/scripts/backup_restore.sh` wraps
  `pg_dump`/`pg_restore` in custom format (compressed, supports parallel
  restore, the standard choice over plain-SQL dumps for anything beyond
  trivial size).

## Verified: a real backup/restore cycle

Run during Phase 5 development, against the actual dev Postgres instance
with real accumulated data (437 vendors, 294 findings, 255 monitoring
alerts at the time):

```
$ ./backup_restore.sh backup "$DSN" tprm_backup.dump
Backing up ... -> tprm_backup.dump
Done. 216K written.

$ createdb tprm_restore_test
$ ./backup_restore.sh restore "$DSN_restore_test" tprm_backup.dump
Restoring tprm_backup.dump -> ...
Restore complete.
```

**Verified after restore:**
- Row counts matched exactly across `vendors` (437), `findings` (294),
  and `monitoring_alerts` (255) — nothing silently dropped.
- The `audit_logs` append-only trigger (`reject_audit_mutation`, Phase 0)
  **survived the dump/restore cycle** — attempting an `UPDATE` against
  the restored database still raised `audit_logs is append-only: UPDATE
  is not permitted`. This matters specifically because `pg_dump`'s
  `--format=custom` output includes functions/triggers by default, but
  it's exactly the kind of thing worth actually checking rather than
  assuming — a restore that silently drops a compliance-critical
  constraint would be worse than no backup at all, since it would *look*
  successful.

This is the actual verification a real production launch checklist item
("test restores monthly," per the Phase 5 spec) should require — a
restore that was never test-restored isn't a verified backup, it's an
assumption.

## Disaster scenarios

### Primary region/AZ down
Not implemented in this build (see RTO table above). The documented path:
RDS Multi-AZ handles same-region AZ failure automatically (`multi_az`
Terraform flag); a full-region failure would need a cross-region read
replica promoted manually, DNS updated, and the app tier redeployed in the
secondary region — none of which exists here. Flagged as a real gap for
whoever operationalizes this beyond a portfolio build, not glossed over.

### Database corrupted
1. Identify when corruption started (audit_logs' immutable trail is the
   first place to look — it can't have been altered after the fact).
2. Restore from the most recent clean backup using
   `backup_restore.sh restore`.
3. Replay any transactions between the backup and the corruption event
   from `audit_logs`, if the RPO gap matters for this specific incident
   (manual process — no automated replay tooling exists).

### Ransomware / compromised credentials
1. RDS automated backups and S3 object versioning are separate from the
   application's own credentials — an attacker with the app's
   `DATABASE_URL` can't delete RDS snapshots (that needs separate AWS
   IAM permissions the app role shouldn't have — verify this in the real
   IAM policy, not assumed from Terraform alone).
2. Restore from the last backup taken *before* the compromise window.
3. Rotate `AUTH_SECRET` (invalidates every active session, vendor and
   staff — see Runbook 10) and every API key in `k8s/02-secret.example.yaml`'s
   key list.
4. Investigate entry point via `audit_logs` before restoring normal
   access — restoring service before understanding how the compromise
   happened just re-exposes the same hole.
