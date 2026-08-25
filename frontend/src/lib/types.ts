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
