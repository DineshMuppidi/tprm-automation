# Evidence Validation Guide

Phase 3 deliverable. How
[`evidence_validator.py`](../../backend/app/services/remediation/evidence_validator.py)
decides whether uploaded evidence actually proves a finding is fixed —
for reviewers who want to understand what the system is (and isn't)
checking, and for anyone extending the heuristic.

## The rule the mock provider encodes

The spec's own example: a vendor claims "MFA required for all admin
accounts" and uploads a screenshot showing MFA enabled on *one* account.
That's evidence of *something*, but not proof of the actual claim (all
accounts). The mock evidence validator (`MockRemediationReviewProvider.
validate_evidence`) encodes exactly this distinction:

| Evidence submitted | Finding severity | Outcome |
|---|---|---|
| None | any | **Reject** — nothing to evaluate |
| Third-party audit/certification (`audit_report`, `penetration_test`, `soc2_type2`, `iso27001_cert`, `pci_aoc`) | any | **Approve** — independently verified, high confidence |
| Screenshot(s) only | critical / high | **Request clarification** — proves a point-in-time config, not org-wide scope |
| Screenshot(s) only | medium / low | **Approve** — lower-stakes findings don't need the same scrutiny |
| Policy document only | any | **Request clarification** — shows intent, not implementation |
| Anything else | any | **Approve** (moderate confidence) |

This is a deliberately simple, explainable ruleset — not a black box. A
real deployment would want more nuance (e.g. distinguishing a screenshot
of an admin console's *organization-wide* MFA policy page from one
account's settings), which needs either a smarter prompt (live/Anthropic
provider) or document-content extraction this build doesn't do yet (OCR/
PDF text extraction — noted as a gap, not attempted).

## Live provider

`AnthropicRemediationReviewProvider` sends the finding's title,
description, required evidence, severity, and a description of what was
submitted to Claude with a system prompt instructing the same strictness
("evidence must demonstrate the fix at the required scope"), asking for
structured JSON with a `recommendation`, `confidence`, `reasoning`, and
optional `follow_up_question`. It doesn't currently send the *file
contents* — only filenames and detected document types — so it's
reasoning about what *kind* of evidence was provided, not what's actually
in the file. Extracting and sending real file content (text from a PDF,
OCR from a screenshot) is the natural next step for a live deployment and
is called out here rather than silently assumed.

## Plan review uses the same pattern

`review_plan` applies the analogous rule for remediation *plans* (before
any evidence exists): does the plan name concrete actions and a timeline,
or is it vague ("we will look into it")? The mock heuristic checks for a
timeline pattern (a date, or "N days/weeks/months") plus a ratio of
concrete-action keywords to hedging keywords — see `_WEAK_PLAN_MARKERS` /
`_STRONG_PLAN_MARKERS` / `_TIMELINE_PATTERN` in `evidence_validator.py`.

## Extending it

Both `review_plan` and `validate_evidence` are single methods on
`RemediationReviewProvider` — adding a new evidence heuristic (e.g.
"reject evidence uploaded more than 1 year after the finding was
identified, it's likely stale") means editing `MockRemediationReviewProvider.
validate_evidence` and adjusting the equivalent prompt instruction in
`AnthropicRemediationReviewProvider`, nothing else in the call chain
changes.
