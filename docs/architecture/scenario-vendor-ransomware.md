# Scenario Walkthrough: Vendor Ransomware Attack Affecting Patient Data

Phase 0 deliverable — the enterprise use case the whole architecture is
built to serve.

**Setup:** A healthcare system uses 500+ third-party vendors, tracked in
`vendors` at various tiers. One of them — a Tier 1 (Critical) vendor
providing an HR/benefits platform that processes employee data including
some health-plan fields — suffers a ransomware attack that affects data
including patient/employee PII.

## Timeline

| Time (T+) | Component invoked | What happens | Manual decision point? |
|---|---|---|---|
| T+0 | External (ransomware group dark-web post, security researcher tweet) | Attack becomes publicly visible before the vendor discloses it | — |
| T+2 min | `daily_news_monitoring` / a faster reputation-check DAG (Phase 2) picks up the story via NewsAPI/RSS | Story ingested into the pipeline | — |
| T+3 min | LLM sentiment/classification (Claude API) | Classifies story type = `breach`/`ransomware`, extracts entity = vendor legal/DBA name, assesses this as material (not a false positive like an unrelated person sharing the vendor's name) | — |
| T+4 min | `hourly_breach_check` DAG cross-references breach databases | Confirms vendor domain/infrastructure appears in recent breach signal sources | — |
| T+5 min | **Impact Assessment automation** (Phase 2 §4) queries `vendor_business_units` | Determines: which business units use this vendor, how many employees, what `data_types` are exposed (per the schema's `affected_user_count` / `data_types[]` columns) | — |
| T+5 min | Compliance-obligation lookup (`contract_obligations`, `control_mappings`) | Determines applicable regulatory triggers — HIPAA (health-plan data present), state breach-notification law, contractual incident-notification SLA (from `contracts.extracted_terms`) | — |
| T+6 min | `monitoring_alerts` row created (`alert_type = breach`, `severity = critical`) → **Playbook Engine** triggers `vendor_breach_response` (Phase 4) | Auto-creates an incident `finding`/ticket, assigns to CISO + Compliance Officer + Legal + affected business-unit owner, drafts a breach-notification template pre-populated with vendor + regulatory context | — |
| T+7 min | Alert routed per Phase 2 escalation config | Critical alert → immediate email + Slack `#incident-response` + SMS to on-call | — |
| T+1 hr | Escalation timer (Phase 2 §7 / §4) | If no acknowledgment within 1 hour, auto-escalate to CISO directly | **Decision:** did the assigned owner actually see and act on this? System escalates either way — it doesn't wait to find out. |
| T+15 min – T+1 hr | Human response begins | Incident commander reviews the auto-pulled packet: vendor contract SLA, prior assessment history (was this vendor already flagged risky?), vendor emergency contact | **Decision:** confirm scope of impact with the vendor directly — this is not automatable, it requires the vendor's own incident report |
| T+1–6 hr | Manual response, system-assisted | Legal uses the pre-drafted notification template; Compliance uses the auto-generated regulatory checklist (HIPAA breach notification timeline, state AG requirements) rather than starting from a blank page | **Decision:** exact notification scope/wording — drafted by the system, approved by Legal |
| T+24 hr | Post-incident automation (Phase 4 playbook step 10) | Risk score recalculated (+severity-weighted delta per `monitoring_alerts.risk_score_delta`), contract renewal flagged for review, post-incident review scheduled for T+30 days | — |
| T+30 days | Scheduled review (playbook-tracked) | Formal post-incident review: was the vendor's remediation plan credible? Does the contract get renewed, renegotiated, or does the org start sourcing a replacement? | **Decision:** renew/renegotiate/replace — a business decision the system informs but does not make |

## Why this shape matters architecturally

- **Detection is fast because it doesn't depend on the vendor telling us.**
  The monitoring tier (news + breach databases) can beat the vendor's own
  disclosure by hours, which is the entire value proposition of Phase 2
  over a purely questionnaire-based TPRM process.
- **The system never takes an autonomous action with legal/regulatory
  consequences.** It drafts, assembles, and routes — notification content,
  scope determination, and the renew/replace decision are all explicitly
  human calls (see threat-model.md §6 for why this is a deliberate
  constraint, not a missing feature).
- **Every step traces to a schema table**, which is why the data model
  (Phase 0 §2) was designed around this scenario specifically:
  `vendor_business_units` for blast-radius, `contract_obligations` for
  "what did we require and did they meet it," `monitoring_alerts` →
  `findings` → `playbook_executions` for the auditable chain from
  detection to closure.
