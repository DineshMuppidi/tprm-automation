import type {
  AlertOut, AssessmentDetail, AssessmentSummary, ExceptionOut, FindingDetail, FindingSummary,
  KPIReport, MonitoringStatusOut, RiskBreakdown, RunChecksOut, TemplateOut, VendorOut, VendorRiskEntry,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const SESSION_KEY = "tprm_session";
const ADMIN_KEY = "tprm_admin_key";

export interface Session {
  access_token: string;
  vendor_id: string;
  vendor_contact_id: string;
  vendor_name: string;
}

export function getSession(): Session | null {
  const raw = localStorage.getItem(SESSION_KEY);
  return raw ? (JSON.parse(raw) as Session) : null;
}

export function setSession(session: Session) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearSession() {
  localStorage.removeItem(SESSION_KEY);
}

export function getAdminKey(): string {
  return localStorage.getItem(ADMIN_KEY) || "";
}

export function setAdminKey(key: string) {
  localStorage.setItem(ADMIN_KEY, key);
}

class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(
  path: string,
  opts: { method?: string; body?: unknown; asAdmin?: boolean; formData?: FormData } = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (opts.asAdmin) {
    headers["X-Admin-Key"] = getAdminKey();
  } else {
    const session = getSession();
    if (session) headers["Authorization"] = `Bearer ${session.access_token}`;
  }

  let body: BodyInit | undefined;
  if (opts.formData) {
    body = opts.formData;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }

  const res = await fetch(`${BASE_URL}${path}`, { method: opts.method || "GET", headers, body });
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(res.status, detail);
  }
  if (res.headers.get("content-type")?.includes("application/pdf")) {
    return (await res.blob()) as unknown as T;
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  requestLink: (email: string) => request<{ message: string }>("/auth/request-link", { method: "POST", body: { email } }),
  verify: (token: string) => request<Session>("/auth/verify", { method: "POST", body: { token } }),

  myAssessments: () => request<AssessmentSummary[]>("/assessments/mine"),
  getAssessment: (id: string) => request<AssessmentDetail>(`/assessments/${id}`),
  saveResponse: (assessmentId: string, questionId: string, rawAnswer: string) =>
    request(`/assessments/${assessmentId}/responses/${questionId}`, { method: "PUT", body: { raw_answer: rawAnswer } }),
  analyzeResponse: (assessmentId: string, questionId: string) =>
    request(`/assessments/${assessmentId}/responses/${questionId}/analyze`, { method: "POST" }),
  uploadEvidence: (assessmentId: string, questionId: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request(`/assessments/${assessmentId}/responses/${questionId}/evidence`, { method: "POST", formData: fd });
  },
  submitAssessment: (id: string) => request<AssessmentDetail>(`/assessments/${id}/submit`, { method: "POST" }),
  getRisk: (id: string) => request<RiskBreakdown>(`/assessments/${id}/risk`),

  adminListVendors: () => request<VendorOut[]>("/admin/vendors", { asAdmin: true }),
  adminListTemplates: () => request<TemplateOut[]>("/admin/templates", { asAdmin: true }),
  adminListAssessments: () => request<AssessmentSummary[]>("/admin/assessments", { asAdmin: true }),
  adminCreateVendor: (body: {
    legal_name: string; industry: string; tier: string; data_access_level: string;
    primary_contact: { full_name: string; email: string; role: string };
  }) => request<VendorOut>("/admin/vendors", { method: "POST", body, asAdmin: true }),
  adminAssignAssessment: (vendor_id: string, template_id: string) =>
    request<AssessmentSummary & { dev_login_url?: string | null }>(
      "/admin/assessments", { method: "POST", body: { vendor_id, template_id }, asAdmin: true },
    ),

  listAlerts: (filters: { vendor_id?: string; severity?: string; status?: string; alert_type?: string } = {}) => {
    const params = new URLSearchParams(Object.entries(filters).filter(([, v]) => v) as [string, string][]);
    const qs = params.toString();
    return request<AlertOut[]>(`/admin/monitoring/alerts${qs ? `?${qs}` : ""}`, { asAdmin: true });
  },
  acknowledgeAlert: (id: string) => request<AlertOut>(`/admin/monitoring/alerts/${id}/acknowledge`, { method: "POST", body: {}, asAdmin: true }),
  resolveAlert: (id: string) => request<AlertOut>(`/admin/monitoring/alerts/${id}/resolve`, { method: "POST", asAdmin: true }),
  suppressAlert: (id: string, reason: string) =>
    request<AlertOut>(`/admin/monitoring/alerts/${id}/suppress`, { method: "POST", body: { reason }, asAdmin: true }),
  monitoringStatus: () => request<MonitoringStatusOut>("/admin/monitoring/status", { asAdmin: true }),
  riskScoreboard: () => request<VendorRiskEntry[]>("/admin/monitoring/scoreboard", { asAdmin: true }),
  runMonitoringChecks: () => request<RunChecksOut>("/admin/monitoring/run-checks", { method: "POST", asAdmin: true }),

  // Findings — vendor-facing
  myFindings: () => request<FindingSummary[]>("/findings/mine"),
  getFinding: (id: string) => request<FindingDetail>(`/findings/${id}`),
  acknowledgeFinding: (id: string) => request<FindingDetail>(`/findings/${id}/acknowledge`, { method: "POST" }),
  submitPlan: (id: string, plan_text: string) => request<FindingDetail>(`/findings/${id}/plan`, { method: "PUT", body: { plan_text } }),
  uploadFindingEvidence: (id: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request(`/findings/${id}/evidence`, { method: "POST", formData: fd });
  },
  submitFinding: (id: string) => request<FindingDetail>(`/findings/${id}/submit`, { method: "POST" }),
  addFindingComment: (id: string, body: string, asAdmin = false) =>
    request<FindingDetail>(`/findings/${id}/comments`, { method: "POST", body: { body }, asAdmin }),
  requestException: (id: string, justification: string, compensating_controls: string) =>
    request<ExceptionOut>(`/findings/${id}/request-exception`, { method: "POST", body: { justification, compensating_controls } }),

  // Findings — admin
  adminListFindings: (filters: { vendor_id?: string; status?: string; severity?: string } = {}) => {
    const params = new URLSearchParams(Object.entries(filters).filter(([, v]) => v) as [string, string][]);
    const qs = params.toString();
    return request<FindingSummary[]>(`/admin/findings${qs ? `?${qs}` : ""}`, { asAdmin: true });
  },
  adminGetFinding: (id: string) => request<FindingDetail>(`/findings/${id}`, { asAdmin: true }),
  adminCloseFinding: (id: string, note: string) => request<FindingDetail>(`/admin/findings/${id}/close`, { method: "POST", body: { note }, asAdmin: true }),
  adminRejectFinding: (id: string, note: string) => request<FindingDetail>(`/admin/findings/${id}/reject`, { method: "POST", body: { note }, asAdmin: true }),
  adminListExceptions: () => request<ExceptionOut[]>("/admin/exceptions", { asAdmin: true }),
  adminApproveException: (id: string) => request<ExceptionOut>(`/admin/exceptions/${id}/approve`, { method: "POST", asAdmin: true }),
  adminRunFindingEscalationCheck: () => request<Record<string, number>>("/admin/findings/run-escalation-check", { method: "POST", asAdmin: true }),
  kpiReport: () => request<KPIReport>("/admin/reporting/kpis", { asAdmin: true }),
};

export { ApiError, BASE_URL };
