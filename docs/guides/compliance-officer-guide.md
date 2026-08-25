# Compliance Officer Guide

Day-to-day operation of the platform from the risk/compliance side.

## Assigning an assessment

`/admin` (admin key required — see your team's password manager entry, or
ask IT for a staff account once the RBAC retrofit covers this endpoint —
see `security-hardening.md`). Pick the vendor, pick the tier-appropriate
template, and assign. The vendor gets an email with a sign-in link
automatically. In a `console`-email dev/demo environment, the assign
response includes a clickable dev link directly (never shown in a real
deployment with SMTP configured).

## Reviewing assessments and closing findings

`/admin/findings` is your daily view: every open finding, filterable by
status/severity, with vendor performance (closure rate, overdue count)
and pending exceptions all in one place.

- **When a vendor submits evidence**, the system already ran its own
  review before you see it — the finding is either `closed` (evidence
  approved) or back to `rejected` (needs more from the vendor) by the
  time you look. You don't have to manually approve every submission;
  your job is reviewing the ones the system flagged as ambiguous, and
  spot-checking the ones it approved.
- **Overriding the automated call**: open the finding at `/admin/findings/{id}`
  — "Close finding" or "Send back for revision" let you override the LLM
  review's recommendation with your own judgment, with a note explaining
  why (visible to the vendor).
- **Exceptions**: the Exceptions tab shows every pending request with the
  vendor's justification and proposed compensating controls. Approving
  one requires a staff session with the `compliance_officer` or `ciso`
  role (not just the admin key) — this is deliberate: risk acceptance is
  a decision that should be attributable to a specific person, and the
  system now records exactly who approved each one.

## Monitoring alerts

`/admin/monitoring` shows the live alert feed, a vendor risk scoreboard,
and data-source health. **Acknowledge** an alert once you've seen it,
**resolve** it once addressed, or **suppress** it (with a reason — expires
automatically in 90 days, so a suppression can't quietly become permanent
without anyone revisiting it) if it's a confirmed false positive.

A critical alert that goes unacknowledged escalates on its own — see
`docs/monitoring/alert-routing.md` for exactly when.

## Board reporting

`/admin/board` is what to pull up for a quarterly review: vendor risk
distribution, remediation KPIs (closure rate, MTTR by severity, rework
rate), the biggest control gaps across your whole vendor base, upcoming
contract renewals, and a log of every automated playbook that's run.

## Contracts

`/admin/contracts` — upload a vendor's contract (PDF or text) and the
platform extracts the security-relevant terms (required certifications,
breach-notification SLA, liability, termination/renewal windows)
automatically. Review the extracted terms for accuracy — this is a
starting point for your own read of the contract, not a substitute for
one; the extraction is regex/LLM-based and can miss unusually-worded
clauses. **"Check compliance"** flags vendors whose certification has
actually expired against what the contract requires.

## When something looks wrong

If a finding's severity or a risk score seems off, check where it came
from — every finding traces back to either a specific assessment response
or a specific monitoring alert (shown on the finding detail page), so you
can see exactly what triggered it rather than taking the number on faith.
