# Training: Compliance Team (2 hours)

Format: slide-outline + hands-on lab, not a script — an instructor fills
in the narrative around each section.

## Session outline

**1. Why this platform exists (10 min)**
- The 1,500-hour/year manual workload problem (see root `README.md`'s
  opening).
- What's automated vs. what still needs judgment: scoring, tracking, and
  escalating are automated; deciding whether a vendor's excuse is
  acceptable, or whether evidence is real, is still yours.

**2. Reviewing assessments (20 min)**
- Walk through `/admin/findings` live.
- How severity and due dates are set automatically (`docs/remediation/
  state-machine.md`'s finding-generation section) — critical: 30 days,
  high: 60, medium: 90, low: 120.
- What "the system already reviewed this" means for evidence submissions
  — you're the exception-handler for ambiguous cases, not a rubber stamp
  for every submission.

**3. Remediation workflow, live demo (30 min)**
- Acknowledge → plan review (show a vague plan getting rejected, then a
  concrete one getting accepted) → evidence → close, using the actual
  demo vendor.
- The rejection/resubmit loop — `rejected` isn't a dead end, walk through
  what the vendor sees on their side (`docs/guides/vendor-guide.md`).
- Manually overriding a decision (close/reject with a note) and when
  that's appropriate.

**4. Exceptions and risk acceptance (15 min)**
- Reviewing a justification + compensating controls.
- Why approval requires your actual staff login now, not just the shared
  admin key — you're the accountable approver on record
  (`security-hardening.md`'s RBAC section).
- Expiry: exceptions aren't permanent; know when yours come up for review.

**5. Monitoring alerts (15 min)**
- Alert Feed walkthrough, severity → who gets notified
  (`docs/monitoring/alert-routing.md`).
- Acknowledge / resolve / suppress, and why suppressions expire.
- What triggers an automatic playbook (`docs/advanced/playbook-engine.md`)
  vs. what needs your manual follow-through.

**6. Board reporting (10 min)**
- `/admin/board` walkthrough — this is what you'll actually present
  quarterly.

**7. Hands-on lab (30 min)**
- Trainees log into the demo environment, work through one full
  assessment-to-closure cycle themselves as the "vendor," then switch to
  the compliance view and review their own submission.
- Intentional: doing both sides once makes the LLM review's behavior
  concrete rather than abstract.

## Materials needed
- Demo environment access (seeded via `db/seed_demo_data.py`).
- This document + `docs/guides/compliance-officer-guide.md` as leave-behind
  reference.
