# Leadership Briefing (30 minutes)

## Slide outline

**1. The problem (2 min)**
- Manual vendor risk management: ~1,500 hours/year across assessment,
  monitoring, and remediation tracking for a mid-size vendor portfolio.
- What that actually costs: slow onboarding, expired certifications
  nobody caught, findings that got "fixed" with a promise instead of
  evidence.

**2. What this platform automates (5 min)**
- One sentence per phase: intake & scoring, continuous monitoring,
  accountable remediation, contract/framework intelligence.
- The one design principle that matters most for a leadership audience:
  automation *informs and routes*, it never makes the risk-acceptance or
  contract-enforcement decision on its own — those stay human, on the
  record (see `docs/operations/security-hardening.md`'s RBAC section for
  the concrete example: exception approval requires a named, authenticated
  approver now).

**3. Dashboard walkthrough (10 min)**
- `/admin/board`, live: vendor risk distribution, remediation velocity,
  top control gaps, contract renewals due, playbook activity log.
- This is the actual quarterly board packet source — not a mockup built
  separately from what the team uses day to day.

**4. Risk register — what's on it right now (5 min)**
- Top 3-5 highest-risk vendors from the live scoreboard.
- Any findings overdue past the Legal-escalation threshold.
- Contracts expiring in the renewal window.

**5. Roadmap (5 min)**
- What's built (Phases 0-5, all committed) vs. documented gaps: data
  retention isn't enforced by a running job yet, GDPR deletion isn't
  built, the RBAC retrofit covers one endpoint as a proven pattern rather
  than all of them, and this build has never been deployed to real cloud
  infrastructure (no Docker/Terraform/Kubernetes execution in the
  development environment — infrastructure-as-code was written and
  reviewed, not run).

**6. Costs & ROI framing (3 min)**
- LLM-backed features default to a free, deterministic mock mode — the
  live-Claude-API path is the only variable cost driver, and it's
  opt-in per feature category (`LLM_PROVIDER` setting), not all-or-nothing.
- Infrastructure costs are Terraform-estimable once a real environment
  exists (`terraform/main.tf`'s `db_instance_class`/`allocated_storage`
  are the main levers) — no real cloud spend has been incurred building
  this.
