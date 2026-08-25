-- ============================================================================
-- TPRM Automation Platform — Core Data Model
-- Phase 0 deliverable. PostgreSQL 15+.
-- ============================================================================
-- Design notes:
--   * UUID PKs (gen_random_uuid) so records are safely referenceable across
--     services (assessment engine, monitoring workers, playbook engine)
--     without a central sequence bottleneck.
--   * All timestamps are timestamptz — vendors and monitoring sources span
--     time zones, and DST bugs in a compliance deadline tracker are a real
--     incident, not a hypothetical.
--   * Enumerations use Postgres ENUM types (not free-text) so invalid states
--     (a typo'd "aproved") are rejected at the schema layer, not caught
--     later in a report to an auditor.
--   * audit_logs is append-only: INSERT is granted, UPDATE/DELETE are
--     revoked from the application role and blocked by trigger. Regulators
--     and auditors need to trust this table cannot be edited after the fact.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS citext;     -- case-insensitive email columns

-- ----------------------------------------------------------------------------
-- Enumerations
-- ----------------------------------------------------------------------------

CREATE TYPE user_role AS ENUM (
    'admin', 'ciso', 'compliance_officer', 'category_manager',
    'vendor_manager', 'legal', 'read_only'
);

CREATE TYPE vendor_tier AS ENUM ('tier_1_critical', 'tier_2_high', 'tier_3_medium', 'tier_4_low');

CREATE TYPE vendor_status AS ENUM (
    'prospective', 'onboarding', 'active', 'under_review',
    'remediation_required', 'suspended', 'offboarding', 'terminated'
);

CREATE TYPE assessment_status AS ENUM (
    'draft', 'assigned', 'in_progress', 'submitted', 'under_review', 'completed', 'expired'
);

CREATE TYPE response_classification AS ENUM (
    'strong', 'adequate', 'weak', 'missing', 'contradictory'
);

CREATE TYPE evidence_status AS ENUM ('unverified', 'verified', 'needs_clarification', 'rejected');

CREATE TYPE finding_severity AS ENUM ('critical', 'high', 'medium', 'low');

-- Mirrors the Phase 3 remediation state machine exactly, so application
-- code cannot introduce a status the workflow engine doesn't know about.
CREATE TYPE finding_status AS ENUM (
    'new', 'assigned', 'in_progress', 'submitted', 'validating',
    'closed', 'rejected', 'overdue', 'exception_granted'
);

CREATE TYPE alert_severity AS ENUM ('critical', 'high', 'medium', 'low');

CREATE TYPE alert_status AS ENUM ('new', 'acknowledged', 'escalated', 'resolved', 'suppressed');

CREATE TYPE alert_type AS ENUM (
    'cert_expiry', 'breach', 'cve', 'news_reputation',
    'financial_distress', 'regulatory', 'contract_violation'
);

CREATE TYPE contract_status AS ENUM ('active', 'expiring_soon', 'expired', 'terminated', 'in_negotiation');

CREATE TYPE document_type AS ENUM (
    'soc2_type1', 'soc2_type2', 'iso27001_cert', 'pci_aoc', 'policy_doc',
    'screenshot', 'audit_report', 'penetration_test', 'contract', 'other'
);

-- ----------------------------------------------------------------------------
-- Organizational structure
-- ----------------------------------------------------------------------------

CREATE TABLE business_units (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL UNIQUE,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           CITEXT NOT NULL UNIQUE,
    full_name       TEXT NOT NULL,
    role            user_role NOT NULL,
    business_unit_id UUID REFERENCES business_units(id),
    is_active       BOOLEAN NOT NULL DEFAULT true,
    mfa_enrolled    BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at   TIMESTAMPTZ
);

-- ----------------------------------------------------------------------------
-- Vendors
-- ----------------------------------------------------------------------------

CREATE TABLE vendors (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    legal_name          TEXT NOT NULL,
    dba_name            TEXT,
    primary_domain      TEXT,                      -- used for HIBP/Shodan/Censys lookups
    industry            TEXT,
    tier                vendor_tier NOT NULL,
    status              vendor_status NOT NULL DEFAULT 'prospective',
    data_access_level   TEXT NOT NULL CHECK (data_access_level IN
                           ('none', 'internal_only', 'confidential', 'restricted_pii', 'phi')),
    risk_score          NUMERIC(5,2) CHECK (risk_score BETWEEN 0 AND 100),
    risk_score_updated_at TIMESTAMPTZ,
    relationship_owner_id UUID REFERENCES users(id),
    category_manager_id UUID REFERENCES users(id),
    onboarded_at        TIMESTAMPTZ,
    offboarded_at       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_vendors_tier_status ON vendors(tier, status);
CREATE INDEX idx_vendors_risk_score ON vendors(risk_score DESC);

CREATE TABLE vendor_contacts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id   UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    full_name   TEXT NOT NULL,
    email       CITEXT NOT NULL,
    role        TEXT,                               -- e.g. "Security Lead", "Account Manager"
    is_primary  BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (vendor_id, email)
);

-- Which internal business units actually use this vendor, and roughly how
-- many people/records are exposed — this is what an impact assessment
-- queries first when a breach alert fires (see Phase 2 scenario).
CREATE TABLE vendor_business_units (
    vendor_id           UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    business_unit_id    UUID NOT NULL REFERENCES business_units(id) ON DELETE CASCADE,
    affected_user_count INTEGER,
    data_types          TEXT[],                     -- e.g. {'pii','payroll','health'}
    PRIMARY KEY (vendor_id, business_unit_id)
);

-- ----------------------------------------------------------------------------
-- Compliance frameworks & control mapping
-- ----------------------------------------------------------------------------

CREATE TABLE frameworks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code        TEXT NOT NULL UNIQUE,                -- 'NIST_CSF_2', 'SOC2', 'ISO27001', 'HIPAA', 'GDPR', 'CIS_V8'
    name        TEXT NOT NULL,
    version     TEXT,
    description TEXT
);

CREATE TABLE controls (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    framework_id    UUID NOT NULL REFERENCES frameworks(id) ON DELETE CASCADE,
    control_ref     TEXT NOT NULL,                   -- e.g. 'CC6.1', 'PR.AC-1', 'A.10.2'
    title           TEXT NOT NULL,
    description     TEXT,
    category        TEXT,                            -- e.g. NIST CSF function: Govern/Protect/Detect/Respond/Recover
    UNIQUE (framework_id, control_ref)
);
CREATE INDEX idx_controls_framework ON controls(framework_id);

-- Undirected semantic equivalence between controls in different frameworks.
-- confidence lets the mapping engine distinguish "these are the same
-- control" from "these are related but not equivalent".
CREATE TABLE control_mappings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    control_a_id    UUID NOT NULL REFERENCES controls(id) ON DELETE CASCADE,
    control_b_id    UUID NOT NULL REFERENCES controls(id) ON DELETE CASCADE,
    confidence      NUMERIC(3,2) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    rationale       TEXT,
    CHECK (control_a_id <> control_b_id),
    UNIQUE (control_a_id, control_b_id)
);

-- ----------------------------------------------------------------------------
-- Questionnaire templates & assessments
-- ----------------------------------------------------------------------------

CREATE TABLE questionnaire_templates (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    tier        vendor_tier NOT NULL,
    version     INTEGER NOT NULL DEFAULT 1,
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE questions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id         UUID NOT NULL REFERENCES questionnaire_templates(id) ON DELETE CASCADE,
    question_code       TEXT NOT NULL,               -- stable ID so trend analysis survives template edits
    section             TEXT NOT NULL,
    prompt              TEXT NOT NULL,
    help_text           TEXT,
    input_type          TEXT NOT NULL CHECK (input_type IN ('text','boolean','select','multiselect','file')),
    options             JSONB,                        -- choices for select/multiselect
    control_id          UUID REFERENCES controls(id),
    scoring_rubric       JSONB,                        -- {"strong": "...", "adequate": "...", "weak": "...", "missing": "..."}
    evidence_required    BOOLEAN NOT NULL DEFAULT false,
    parent_question_id   UUID REFERENCES questions(id), -- for conditional/follow-up branching
    display_order        INTEGER NOT NULL DEFAULT 0,
    UNIQUE (template_id, question_code)
);
CREATE INDEX idx_questions_template ON questions(template_id);

CREATE TABLE assessments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id       UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    template_id     UUID NOT NULL REFERENCES questionnaire_templates(id),
    status          assessment_status NOT NULL DEFAULT 'draft',
    assigned_at     TIMESTAMPTZ,
    due_at          TIMESTAMPTZ,
    submitted_at    TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    overall_score   NUMERIC(5,2) CHECK (overall_score BETWEEN 0 AND 100),
    reviewer_id     UUID REFERENCES users(id),
    reviewed_at     TIMESTAMPTZ,
    prior_assessment_id UUID REFERENCES assessments(id),  -- trend analysis chain
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_assessments_vendor ON assessments(vendor_id, status);
CREATE INDEX idx_assessments_due ON assessments(due_at) WHERE status NOT IN ('completed','expired');

CREATE TABLE assessment_responses (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id       UUID NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    question_id         UUID NOT NULL REFERENCES questions(id),
    raw_answer          TEXT,
    classification       response_classification,
    confidence_score      NUMERIC(5,2) CHECK (confidence_score BETWEEN 0 AND 100),
    extracted_claims      JSONB,                        -- LLM-extracted key statements
    evidence_status        evidence_status NOT NULL DEFAULT 'unverified',
    follow_up_needed       BOOLEAN NOT NULL DEFAULT false,
    follow_up_question     TEXT,
    analyzed_at             TIMESTAMPTZ,                  -- when the LLM analysis ran
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (assessment_id, question_id)
);
CREATE INDEX idx_responses_assessment ON assessment_responses(assessment_id);
CREATE INDEX idx_responses_classification ON assessment_responses(classification);

CREATE TABLE assessment_evidence (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id   UUID NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    response_id     UUID REFERENCES assessment_responses(id) ON DELETE CASCADE,
    document_type   document_type NOT NULL,
    storage_uri     TEXT NOT NULL,                 -- S3 object key; never store raw file bytes in Postgres
    original_filename TEXT NOT NULL,
    extracted_metadata JSONB,                      -- e.g. {"audit_date": "...", "auditor": "...", "controls_covered": [...]}
    uploaded_by_vendor_contact_id UUID REFERENCES vendor_contacts(id),
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_evidence_assessment ON assessment_evidence(assessment_id);

-- ----------------------------------------------------------------------------
-- Findings & remediation (Phase 3 workflow engine persists here)
-- ----------------------------------------------------------------------------

CREATE TABLE findings (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id           UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    source_assessment_id UUID REFERENCES assessments(id),
    source_alert_id      UUID,                          -- FK added after monitoring_alerts is defined below
    control_id           UUID REFERENCES controls(id),
    title                 TEXT NOT NULL,
    description            TEXT NOT NULL,
    risk_rationale          TEXT,                          -- why this matters, shown to vendor
    required_evidence        TEXT,
    severity                 finding_severity NOT NULL,
    status                    finding_status NOT NULL DEFAULT 'new',
    vendor_owner_contact_id   UUID REFERENCES vendor_contacts(id),
    internal_owner_id         UUID REFERENCES users(id),
    due_at                    TIMESTAMPTZ NOT NULL,
    acknowledged_at            TIMESTAMPTZ,
    submitted_at                TIMESTAMPTZ,
    closed_at                    TIMESTAMPTZ,
    rejection_count               INTEGER NOT NULL DEFAULT 0,
    created_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_findings_vendor_status ON findings(vendor_id, status);
CREATE INDEX idx_findings_due ON findings(due_at) WHERE status NOT IN ('closed','rejected','exception_granted');
CREATE INDEX idx_findings_severity_status ON findings(severity, status);

CREATE TABLE remediation_evidence (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id      UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    document_type   document_type NOT NULL,
    storage_uri     TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    llm_validation_result JSONB,     -- {"recommendation": "approve|clarify|reject", "reasoning": "...", "confidence": 0.0-1.0}
    reviewed_by_id  UUID REFERENCES users(id),
    reviewed_at     TIMESTAMPTZ,
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_remediation_evidence_finding ON remediation_evidence(finding_id);

-- Formal risk-acceptance workflow when a vendor cannot remediate a finding.
CREATE TABLE exceptions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id          UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    justification        TEXT NOT NULL,
    compensating_controls TEXT,
    approved_by_id         UUID REFERENCES users(id),
    approved_at              TIMESTAMPTZ,
    expires_at                TIMESTAMPTZ NOT NULL,          -- exceptions must be revisited (spec: 12 months)
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_exceptions_expiry ON exceptions(expires_at);

-- ----------------------------------------------------------------------------
-- Contracts
-- ----------------------------------------------------------------------------

CREATE TABLE contracts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id           UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    contract_name        TEXT NOT NULL,
    storage_uri            TEXT NOT NULL,
    status                  contract_status NOT NULL DEFAULT 'active',
    effective_date            DATE NOT NULL,
    expiration_date             DATE,
    auto_renews                  BOOLEAN NOT NULL DEFAULT false,
    renewal_notice_days            INTEGER,                      -- e.g. 60
    extracted_terms                  JSONB,     -- SLA, incident SLA, security reqs, audit rights, liability, termination
    parsed_at                          TIMESTAMPTZ,
    created_at                          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_contracts_vendor ON contracts(vendor_id);
CREATE INDEX idx_contracts_expiration ON contracts(expiration_date) WHERE status = 'active';

-- Individual, trackable obligations extracted from a contract — each one
-- is periodically checked for compliance (e.g. "quarterly SOX testing").
CREATE TABLE contract_obligations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id         UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    description          TEXT NOT NULL,
    obligation_type        TEXT NOT NULL CHECK (obligation_type IN
                              ('certification','audit','notification_sla','sla_uptime','other')),
    check_frequency          TEXT CHECK (check_frequency IN ('once','monthly','quarterly','annually')),
    control_id                UUID REFERENCES controls(id),
    last_checked_at              TIMESTAMPTZ,
    last_check_status              TEXT CHECK (last_check_status IN ('compliant','non_compliant','unknown')),
    next_check_due                   TIMESTAMPTZ
);
CREATE INDEX idx_obligations_next_check ON contract_obligations(next_check_due);

-- ----------------------------------------------------------------------------
-- Continuous monitoring
-- ----------------------------------------------------------------------------

CREATE TABLE monitoring_sources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            TEXT NOT NULL UNIQUE,             -- 'soc2_registry','hibp','shodan','newsapi','dnb', etc.
    name            TEXT NOT NULL,
    is_enabled      BOOLEAN NOT NULL DEFAULT true,
    last_checked_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    last_error      TEXT
);

CREATE TABLE monitoring_alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id       UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    source_id       UUID REFERENCES monitoring_sources(id),
    alert_type      alert_type NOT NULL,
    severity        alert_severity NOT NULL,
    status          alert_status NOT NULL DEFAULT 'new',
    title           TEXT NOT NULL,
    payload         JSONB NOT NULL,                  -- raw + enriched detection detail
    risk_score_delta NUMERIC(5,2),
    acknowledged_by_id UUID REFERENCES users(id),
    acknowledged_at TIMESTAMPTZ,
    escalated_at    TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_alerts_vendor_status ON monitoring_alerts(vendor_id, status);
CREATE INDEX idx_alerts_severity_status ON monitoring_alerts(severity, status);
CREATE INDEX idx_alerts_detected ON monitoring_alerts(detected_at DESC);

ALTER TABLE findings ADD CONSTRAINT fk_findings_source_alert
    FOREIGN KEY (source_alert_id) REFERENCES monitoring_alerts(id);

CREATE TABLE alert_suppressions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id       UUID REFERENCES vendors(id) ON DELETE CASCADE,
    alert_type      alert_type,
    match_pattern   TEXT,                            -- e.g. news keyword pattern being suppressed
    reason          TEXT NOT NULL,
    created_by_id   UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL              -- suppressions expire and must be re-justified (spec: 90 days)
);
CREATE INDEX idx_suppressions_expiry ON alert_suppressions(expires_at);

-- ----------------------------------------------------------------------------
-- Playbooks (definitions land in Phase 0/4; executions logged from Phase 2+)
-- ----------------------------------------------------------------------------

CREATE TABLE playbook_definitions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            TEXT NOT NULL UNIQUE,             -- 'vendor_breach_response', 'cert_expiring', ...
    name            TEXT NOT NULL,
    trigger_event   TEXT NOT NULL,                    -- e.g. 'alert.breach', 'alert.cert_expiry_30d'
    steps           JSONB NOT NULL,                   -- ordered step definitions
    is_active       BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE playbook_executions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    playbook_id     UUID NOT NULL REFERENCES playbook_definitions(id),
    vendor_id       UUID REFERENCES vendors(id),
    triggered_by_alert_id UUID REFERENCES monitoring_alerts(id),
    triggered_by_finding_id UUID REFERENCES findings(id),
    status          TEXT NOT NULL CHECK (status IN ('running','completed','failed')) DEFAULT 'running',
    step_log        JSONB NOT NULL DEFAULT '[]',
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ
);
CREATE INDEX idx_playbook_exec_vendor ON playbook_executions(vendor_id);

-- ----------------------------------------------------------------------------
-- Audit log — immutable
-- ----------------------------------------------------------------------------

CREATE TABLE audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    actor_user_id   UUID REFERENCES users(id),
    actor_vendor_contact_id UUID REFERENCES vendor_contacts(id),
    action          TEXT NOT NULL,                    -- e.g. 'finding.status_changed', 'evidence.uploaded'
    entity_type     TEXT NOT NULL,
    entity_id       UUID NOT NULL,
    before_state    JSONB,
    after_state     JSONB,
    ip_address      INET,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_occurred ON audit_logs(occurred_at DESC);

CREATE OR REPLACE FUNCTION reject_audit_mutation() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs is append-only: % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_logs_no_update
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation();

-- ============================================================================
-- Retention policy (enforced by a scheduled job, not by the schema itself —
-- documented here so the two never drift apart):
--   * assessment_responses / assessment_evidence : retained 3 years post-
--     assessment completion, then archived to cold storage (S3 Glacier) and
--     purged from Postgres.
--   * findings / remediation_evidence            : retained 3 years after
--     closed_at.
--   * contracts / contract_obligations            : retained 7 years after
--     expiration_date (standard contract statute-of-limitations window).
--   * monitoring_alerts                            : retained 2 years, then
--     summarized into monthly aggregates for trend charts.
--   * audit_logs                                    : retained 7 years,
--     never deleted by application code — only by a documented, logged
--     manual archival procedure.
--   * GDPR "right to be forgotten" requests override the above for a given
--     vendor_contact's personal data (name/email) via anonymization, not
--     row deletion — the audit trail itself must survive.
-- ============================================================================
