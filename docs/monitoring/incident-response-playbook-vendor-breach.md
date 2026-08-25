# Incident Response Playbook: Vendor Breach

Phase 2 deliverable. This is the one playbook Phase 2 actually implements
end to end (Phase 2 spec §6's ransomware scenario); Phase 4 generalizes
this pattern into a templated, multi-playbook engine (`playbook_definitions`
/ `playbook_executions` in the schema) covering the other four playbooks
the full spec describes (cert expiring, critical assessment failure,
financial distress, remediation deadline missed). Building the generic
engine now, before a second real playbook exists to generalize from, would
be designing against a guess — this document and the code behind it are
that first real case.

## Trigger

A `breach` alert reaches `severity = critical` in `monitoring_alerts`
(raised by `hourly_breach_check` — see
[`alert-routing.md`](alert-routing.md) for how a signal gets there).

## Steps

| # | Step | Automated? | Where |
|---|---|---|---|
| 1 | Detect the breach signal (dark-web monitoring, breach database, press coverage) | ✅ Automated | `mock_providers.MockBreachProvider` / `live_providers.LiveBreachProvider` |
| 2 | Persist the alert, dedup against any already-open breach alert for this vendor | ✅ Automated | `alert_engine.raise_alert` |
| 3 | Update the vendor's risk score (+25, per the spec's own worked example) | ✅ Automated | `alert_engine.raise_alert` |
| 4 | Notify stakeholders (CISO, Compliance Officer, Category Manager, Legal — critical severity routes to all four) | ✅ Automated | `alert_engine._recipients_for` + `email_service.send_alert_notification` |
| 5 | Impact assessment: which business units use this vendor, how many people, what data types | ✅ Automated | `impact_assessor.assess_breach_impact` |
| 6 | Determine applicable regulations (HIPAA if PHI involved, state breach-notification law if PII) | ✅ Automated (heuristic — see caveat below) | `impact_assessor.assess_breach_impact` |
| 7 | Pull the contract's incident-notification SLA, if one is on file | ✅ Automated (returns "not on file" until Phase 4 parses contracts) | `impact_assessor.assess_breach_impact` |
| 8 | Auto-create a critical incident finding with the above context | ✅ Automated | `impact_assessor.create_incident_finding` |
| 9 | Escalate to CISO directly if the alert isn't acknowledged within 60 minutes | ✅ Automated | `alert_engine.run_escalation_check` |
| 10 | Confirm the actual scope of impact directly with the vendor | ❌ Manual — requires the vendor's own incident report | Incident commander, using the finding created in step 8 as the starting packet |
| 11 | Draft and send breach notifications to affected individuals/regulators | ❌ Manual — Legal drafts, using the regulations identified in step 6 | Not automated: notification wording carries legal liability and is a deliberate human-in-the-loop point (see the Phase 0 threat model's stance on this) |
| 12 | Decide: renew, renegotiate, or replace this vendor | ❌ Manual — a business decision the system informs, never makes | Post-incident review, ~30 days out |

## Caveat on step 6 (regulation mapping)

The current heuristic is intentionally simple: `data_types` containing
`"phi"` (or the vendor's `data_access_level` being `phi`) triggers a HIPAA
flag; `"pii"` or `"payroll"` triggers a generic "state breach notification
laws" flag. This is a starting point for a human to verify, not a legal
determination — a real compliance program still needs a lawyer to confirm
which specific state laws apply. Phase 4's cross-framework control mapping
gives this a more rigorous foundation once it's built.

## Where this diverges from a fully "templated" playbook

Steps 1–9 are hardcoded Python control flow (in `alert_engine.py` and
`impact_assessor.py`), not driven by a row in `playbook_definitions`. That
table exists in the schema (Phase 0) for Phase 4 to populate once there's
more than one playbook to generalize across — pointing it at this scenario
today would mean designing the templating scheme from a sample size of
one, which tends to produce the wrong abstraction.
