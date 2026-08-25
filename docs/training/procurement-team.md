# Training: Procurement Team (1 hour)

## Session outline

**1. How risk scores factor into vendor selection (15 min)**
- Risk score bands: <40 low (green), 40-70 medium (yellow), >70 high
  (red) — same bands everywhere in the platform, from the monitoring
  scoreboard to the board dashboard.
- A vendor's score reflects both their assessment answers *and* ongoing
  monitoring signals (a clean assessment doesn't mean a clean score
  forever — a breach alert moves it immediately).
- Where to check a vendor's current score before finalizing a deal:
  `/admin/monitoring` scoreboard, or `/admin/board`'s high-risk-vendor list.

**2. Contract renewals (20 min)**
- `/admin/contracts`: uploading a contract, what gets extracted
  automatically (security requirements, breach-notification SLA,
  liability, termination/renewal windows).
- The board dashboard's "Contract Renewals Due" tab — what's coming up in
  the next 90 days, and why that window (matches the spec's own
  60-day-notice renewal scenario with margin to actually negotiate).
- Reviewing extracted terms for accuracy before relying on them — this is
  a starting point for your read of the contract, not a substitute.

**3. Escalation procedures — when to involve Legal (15 min)**
- A finding overdue 14+ days auto-escalates to Legal already
  (`docs/operations/runbooks.md`'s escalation logic) — you'll be looped
  in on that, not asked to initiate it.
- When *you* should proactively flag something: a vendor with a declining
  score heading into a renewal negotiation, or a vendor requesting
  repeated exceptions on the same control.

**4. Q&A / hands-on (10 min)**
- Walk through the demo vendor's contract and renewal status live.
