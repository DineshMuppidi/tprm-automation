-- Phase 3: remediation workflow additions.
--
-- schema.sql (Phase 0) stays the untouched historical record of the
-- initial design; from here on, each phase that needs new columns/tables
-- ships an additive, idempotent migration here instead of editing it in
-- place. Applied automatically by db/init_db.py, tracked in
-- schema_migrations so re-running is a no-op.

ALTER TABLE findings ADD COLUMN IF NOT EXISTS remediation_plan TEXT;
ALTER TABLE findings ADD COLUMN IF NOT EXISTS remediation_plan_submitted_at TIMESTAMPTZ;
-- LLM plan-credibility review result: {"credible": bool, "reasoning": "...", "follow_up_question": "..."}
ALTER TABLE findings ADD COLUMN IF NOT EXISTS remediation_plan_review JSONB;

-- Vendor <-> internal messaging thread on a finding (spec's "Chat" /
-- "History: view prior interactions" requirement). A generic thread
-- rather than a bespoke request/response pair, so system-generated
-- messages (an auto follow-up question from evidence validation) and
-- human messages share one timeline.
CREATE TABLE IF NOT EXISTS finding_comments (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id              UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    author_type             TEXT NOT NULL CHECK (author_type IN ('vendor', 'internal', 'system')),
    author_vendor_contact_id UUID REFERENCES vendor_contacts(id),
    author_user_id          UUID REFERENCES users(id),
    body                    TEXT NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_finding_comments_finding ON finding_comments(finding_id);
