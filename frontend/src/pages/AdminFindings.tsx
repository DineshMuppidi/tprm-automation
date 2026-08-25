import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import AdminGate from "../components/AdminGate";
import { FindingStatusBadge, SeverityBadge } from "../components/finding/StatusBadge";
import KPICards from "../components/finding/KPICards";
import { api } from "../lib/api";
import type { ExceptionOut, FindingSummary, KPIReport } from "../lib/types";

type Tab = "findings" | "vendors" | "exceptions";

function AdminFindingsBody() {
  const [tab, setTab] = useState<Tab>("findings");
  const [findings, setFindings] = useState<FindingSummary[] | null>(null);
  const [kpis, setKpis] = useState<KPIReport | null>(null);
  const [exceptions, setExceptions] = useState<ExceptionOut[] | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const navigate = useNavigate();

  function refresh() {
    api.adminListFindings().then(setFindings);
    api.kpiReport().then(setKpis);
    api.adminListExceptions().then(setExceptions);
  }
  useEffect(refresh, []);

  async function handleApproveException(id: string) {
    await api.adminApproveException(id);
    refresh();
  }

  async function handleRunEscalation() {
    await api.adminRunFindingEscalationCheck();
    refresh();
  }

  const filtered = (findings ?? []).filter((f) => {
    if (statusFilter && f.status !== statusFilter) return false;
    if (severityFilter && f.severity !== severityFilter) return false;
    return true;
  });

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="font-semibold text-slate-900">TPRM Findings & Remediation</span>
            <a href="/admin/monitoring" className="text-sm text-blue-600 hover:underline">Monitoring →</a>
            <a href="/admin" className="text-sm text-blue-600 hover:underline">Assign assessments →</a>
          </div>
          <button onClick={handleRunEscalation} className="rounded-md bg-slate-700 text-white text-sm px-3 py-1.5 hover:bg-slate-800">
            Run escalation check
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6 space-y-4">
        {kpis && <KPICards kpis={kpis} />}

        <div className="flex gap-1 border-b border-slate-200">
          {(["findings", "vendors", "exceptions"] as Tab[]).map((t) => (
            <button
              key={t} onClick={() => setTab(t)}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
                tab === t ? "border-blue-600 text-blue-600" : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              {t === "findings" ? "All Findings" : t === "vendors" ? "Vendor Performance" : `Exceptions${exceptions?.length ? ` (${exceptions.length})` : ""}`}
            </button>
          ))}
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-6">
          {tab === "findings" && (
            <div className="space-y-3">
              <div className="flex gap-2">
                <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-md border border-slate-300 p-1.5 text-sm">
                  <option value="">All statuses</option>
                  {["new", "assigned", "in_progress", "submitted", "validating", "closed", "rejected", "overdue", "exception_granted"].map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)} className="rounded-md border border-slate-300 p-1.5 text-sm">
                  <option value="">All severities</option>
                  {["critical", "high", "medium", "low"].map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-slate-400 text-xs uppercase">
                    <th className="pb-2">Vendor</th><th className="pb-2">Title</th>
                    <th className="pb-2">Severity</th><th className="pb-2">Status</th><th className="pb-2">Due</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((f) => (
                    <tr key={f.id} className="border-t border-slate-100 cursor-pointer hover:bg-slate-50" onClick={() => navigate(`/admin/findings/${f.id}`)}>
                      <td className="py-1.5">{f.vendor_name}</td>
                      <td className="py-1.5 text-slate-600">{f.title.slice(0, 60)}</td>
                      <td className="py-1.5"><SeverityBadge severity={f.severity} /></td>
                      <td className="py-1.5"><FindingStatusBadge status={f.status} /></td>
                      <td className="py-1.5 text-slate-500">{new Date(f.due_at).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {tab === "vendors" && kpis && (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 text-xs uppercase">
                  <th className="pb-2">Vendor</th><th className="pb-2 text-right">Total</th>
                  <th className="pb-2 text-right">Closed</th><th className="pb-2 text-right">Overdue</th>
                  <th className="pb-2 text-right">Closure Rate</th>
                </tr>
              </thead>
              <tbody>
                {kpis.vendor_performance.map((v) => (
                  <tr key={v.vendor_id} className="border-t border-slate-100">
                    <td className="py-1.5">{v.legal_name}</td>
                    <td className="py-1.5 text-right">{v.total_findings}</td>
                    <td className="py-1.5 text-right">{v.closed}</td>
                    <td className="py-1.5 text-right">{v.overdue > 0 ? <span className="text-red-600 font-medium">{v.overdue}</span> : 0}</td>
                    <td className="py-1.5 text-right">{v.closure_rate_pct.toFixed(0)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {tab === "exceptions" && (
            <div className="space-y-3">
              {exceptions?.length === 0 && <p className="text-sm text-slate-400">No pending exception requests.</p>}
              {exceptions?.map((e) => (
                <div key={e.id} className="rounded-md border border-slate-200 p-3">
                  <p className="text-sm text-slate-700">{e.justification}</p>
                  {e.compensating_controls && <p className="text-sm text-slate-500 mt-1">Compensating controls: {e.compensating_controls}</p>}
                  <div className="mt-2 flex items-center gap-3">
                    <button onClick={() => navigate(`/admin/findings/${e.finding_id}`)} className="text-xs text-blue-600 hover:underline">
                      View finding →
                    </button>
                    {!e.approved_at && (
                      <button onClick={() => handleApproveException(e.id)} className="rounded bg-slate-700 text-white text-xs px-2 py-1">
                        Approve exception
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default function AdminFindings() {
  return (
    <AdminGate probe={() => api.kpiReport()}>
      <AdminFindingsBody />
    </AdminGate>
  );
}
