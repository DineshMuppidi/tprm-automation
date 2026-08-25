export type Classification = "strong" | "adequate" | "weak" | "missing" | "contradictory";
export type EvidenceStatus = "verified" | "unverified" | "needs_clarification" | "rejected";

export interface QuestionOptions {
  choices?: string[];
  condition?: { question_code: string; equals: string };
}

export interface Question {
  id: string;
  question_code: string;
  section: string;
  prompt: string;
  help_text: string | null;
  input_type: "text" | "select" | "boolean" | "multiselect" | "file";
  options: QuestionOptions | null;
  evidence_required: boolean;
  display_order: number;
}

export interface Analysis {
  classification: Classification | null;
  confidence_score: number | null;
  extracted_claims: string[] | null;
  evidence_status: EvidenceStatus;
  follow_up_needed: boolean;
  follow_up_question: string | null;
  analyzed_at: string | null;
}

export interface ResponseOut {
  id: string | null;
  question_id: string;
  raw_answer: string | null;
  analysis: Analysis;
}

export interface EvidenceOut {
  id: string;
  response_id: string | null;
  document_type: string;
  original_filename: string;
  uploaded_at: string;
}

export interface AssessmentSummary {
  id: string;
  vendor_id: string;
  vendor_name: string;
  template_name: string;
  tier: string;
  status: string;
  assigned_at: string | null;
  due_at: string | null;
  completed_at: string | null;
  overall_score: number | null;
  progress_pct: number;
  dev_login_url?: string | null;
}

export interface AssessmentDetail extends AssessmentSummary {
  questions: Question[];
  responses: Record<string, ResponseOut>;
  evidence: EvidenceOut[];
}

export interface ControlScore {
  control_id: string;
  control_ref: string;
  control_title: string;
  framework_code: string;
  score: number;
  question_count: number;
}

export interface RiskBreakdown {
  assessment_id: string;
  overall_score: number;
  vendor_risk_score: number;
  classification_counts: Record<string, number>;
  control_scores: ControlScore[];
  framework_scores: Record<string, number>;
}

export interface VendorOut {
  id: string;
  legal_name: string;
  tier: string;
  status: string;
  risk_score: number | null;
}

export interface TemplateOut {
  id: string;
  name: string;
  tier: string;
  question_count: number;
}

export type AlertSeverity = "critical" | "high" | "medium" | "low";
export type AlertStatus = "new" | "acknowledged" | "escalated" | "resolved" | "suppressed";

export interface AlertOut {
  id: string;
  vendor_id: string;
  vendor_name: string;
  alert_type: string;
  severity: AlertSeverity;
  status: AlertStatus;
  title: string;
  payload: Record<string, unknown>;
  risk_score_delta: number | null;
  detected_at: string;
  acknowledged_at: string | null;
  escalated_at: string | null;
  resolved_at: string | null;
}

export interface MonitoringSourceStatus {
  code: string;
  name: string;
  is_enabled: boolean;
  last_checked_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
}

export interface MonitoringStats {
  alerts_this_week: number;
  escalated_this_week: number;
  resolved_this_week: number;
  avg_ack_minutes: number | null;
}

export interface MonitoringStatusOut {
  sources: MonitoringSourceStatus[];
  stats: MonitoringStats;
}

export interface RunChecksOut {
  cert_expiry: number;
  breach_cve: number;
  news: number;
  financial: number;
  escalations: number;
  ran_at: string;
}

export interface VendorRiskEntry {
  id: string;
  legal_name: string;
  tier: string;
  status: string;
  risk_score: number | null;
  open_alert_count: number;
}

export type FindingSeverity = "critical" | "high" | "medium" | "low";
export type FindingStatus =
  | "new" | "assigned" | "in_progress" | "submitted" | "validating"
  | "closed" | "rejected" | "overdue" | "exception_granted";

export interface FindingSummary {
  id: string;
  vendor_id: string;
  vendor_name: string;
  title: string;
  severity: FindingSeverity;
  status: FindingStatus;
  due_at: string;
  created_at: string;
}

export interface FindingComment {
  id: string;
  author_type: "vendor" | "internal" | "system";
  body: string;
  created_at: string;
}

export interface FindingEvidence {
  id: string;
  document_type: string;
  original_filename: string;
  llm_validation_result: { recommendation: string; confidence: number; reasoning: string } | null;
  uploaded_at: string;
}

export interface FindingDetail extends FindingSummary {
  description: string;
  risk_rationale: string | null;
  required_evidence: string | null;
  remediation_plan: string | null;
  remediation_plan_review: { credible: boolean; reasoning: string; follow_up_question: string | null } | null;
  rejection_count: number;
  acknowledged_at: string | null;
  submitted_at: string | null;
  closed_at: string | null;
  control_ref: string | null;
  control_title: string | null;
  comments: FindingComment[];
  evidence: FindingEvidence[];
}

export interface ExceptionOut {
  id: string;
  finding_id: string;
  justification: string;
  compensating_controls: string | null;
  approved_by_id: string | null;
  approved_at: string | null;
  expires_at: string;
  created_at: string;
}

export interface KPIReport {
  remediation_velocity: {
    by_status: Record<string, number>;
    mttr_days: number | null;
    mttr_by_severity: Record<string, number>;
    closed_last_30_days: number;
  };
  vendor_performance: {
    vendor_id: string; legal_name: string; total_findings: number;
    closed: number; overdue: number; closure_rate_pct: number;
  }[];
  quality: { rework_rate_pct: number; exception_rate_pct: number };
  risk_and_regulatory: {
    avg_vendor_risk_score: number | null;
    vendor_risk_band_counts: { low: number; medium: number; high: number };
    evidence_coverage_pct: number;
  };
}
