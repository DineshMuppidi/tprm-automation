# Post-Launch Retrospective Template

Fill this in ~30 days after a real production launch (or after any phase
of this project a reader wants to retrospect on — the format works at
either scale). Blank template — no invented "we shipped great, 10/10"
example filled in here.

## What shipped

- Date range covered:
- Version(s) deployed:
- Who was on call:

## What went well

-
-

## What didn't go as planned

- Incident/issue:
  - Detected via: (alert? user report? metric?)
  - Time to detect:
  - Time to resolve:
  - Root cause:
  - Runbook used (if any), and did it actually match reality:

## Metrics vs. targets

| Metric | Target | Actual |
|---|---|---|
| Uptime | | |
| P95 API latency | <2s (warning threshold, see monitoring-observability.md) | |
| Findings closure rate | | |
| Alert false-positive rate | | |
| Any 429-related complaints | | |

## Gaps found that weren't in the pre-launch checklist

-

## Action items

| Item | Owner | Due |
|---|---|---|
| | | |

## Should the deferred items get reprioritized?

Revisit `docs/operations/security-hardening.md`'s deferred list (RBAC
retrofit scope, data retention enforcement, GDPR deletion, SAST) against
what actually happened this period — did any of them almost matter?
