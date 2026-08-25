import type { FindingDetail } from "../../lib/types";
import { FindingStatusBadge, SeverityBadge } from "./StatusBadge";

export default function FindingInfoPanel({ finding }: { finding: FindingDetail }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-5 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <SeverityBadge severity={finding.severity} />
            <FindingStatusBadge status={finding.status} />
          </div>
          <h1 className="font-semibold text-slate-900">{finding.title}</h1>
        </div>
        <div className="text-right text-xs text-slate-500 shrink-0">
          <div>Due {new Date(finding.due_at).toLocaleDateString()}</div>
          {finding.control_ref && <div>{finding.control_ref} — {finding.control_title}</div>}
        </div>
      </div>

      <p className="text-sm text-slate-700">{finding.description}</p>
      {finding.risk_rationale && (
        <p className="text-sm text-slate-500"><span className="font-medium text-slate-600">Why this matters: </span>{finding.risk_rationale}</p>
      )}
      {finding.required_evidence && (
        <p className="text-sm text-slate-500"><span className="font-medium text-slate-600">Required evidence: </span>{finding.required_evidence}</p>
      )}

      {finding.remediation_plan && (
        <div className="rounded-md bg-slate-50 border border-slate-200 p-3">
          <p className="text-xs font-medium text-slate-500 uppercase mb-1">Remediation Plan</p>
          <p className="text-sm text-slate-700 whitespace-pre-wrap">{finding.remediation_plan}</p>
          {finding.remediation_plan_review && (
            <p className="text-xs text-slate-400 mt-1">
              {finding.remediation_plan_review.credible ? "✓ Accepted" : "⚠ Needs revision"} — {finding.remediation_plan_review.reasoning}
            </p>
          )}
        </div>
      )}

      {finding.evidence.length > 0 && (
        <div>
          <p className="text-xs font-medium text-slate-500 uppercase mb-1">Evidence Submitted</p>
          <ul className="space-y-1">
            {finding.evidence.map((e) => (
              <li key={e.id} className="text-sm text-slate-600 flex items-center gap-1.5">
                📎 {e.original_filename} <span className="text-slate-400">({e.document_type})</span>
                {e.llm_validation_result && (
                  <span className="text-xs text-slate-400">— {e.llm_validation_result.recommendation}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
