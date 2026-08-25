import { useEffect, useState } from "react";
import AdminGate from "../components/AdminGate";
import KPICards from "../components/finding/KPICards";
import VendorCoveragePanel from "../components/board/VendorCoveragePanel";
import { api } from "../lib/api";
import type { BoardSummary, PlaybookExecution } from "../lib/types";

type Tab = "overview" | "control-gaps" | "renewals" | "playbooks" | "coverage";

function BoardDashboardBody() {
  const [tab, setTab] = useState<Tab>("overview");
  const [summary, setSummary] = useState<BoardSummary | null>(null);
  const [executions, setExecutions] = useState<PlaybookExecution[] | null>(null);

  useEffect(() => {
    api.boardSummary().then(setSummary);
    api.listPlaybookExecutions().then(setExecutions);
  }, []);

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center gap-4">
          <span className="font-semibold text-slate-900">TPRM Board Reporting</span>
          <a href="/admin/findings" className="text-sm text-blue-600 hover:underline">Findings →</a>
          <a href="/admin/monitoring" className="text-sm text-blue-600 hover:underline">Monitoring →</a>
          <a href="/admin/contracts" className="text-sm text-blue-600 hover:underline">Contracts →</a>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6 space-y-4">
        {summary && (
          <div className="grid grid-cols-4 gap-3">
            <Stat label="Total Vendors" value={summary.vendor_risk_distribution.total} />
            <Stat label="Critical Risk" value={summary.vendor_risk_distribution.critical} accent="text-red-600" />
            <Stat label="High Risk" value={summary.vendor_risk_distribution.high} accent="text-amber-600" />
            <Stat label="Low Risk" value={summary.vendor_risk_distribution.low} accent="text-green-600" />
          </div>
        )}

        <div className="flex gap-1 border-b border-slate-200 flex-wrap">
          {(["overview", "control-gaps", "renewals", "playbooks", "coverage"] as Tab[]).map((t) => (
            <button
              key={t} onClick={() => setTab(t)}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
                tab === t ? "border-blue-600 text-blue-600" : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              {{
                overview: "Overview", "control-gaps": "Control Gaps", renewals: "Contract Renewals",
                playbooks: "Playbook Executions", coverage: "Vendor Coverage",
              }[t]}
            </button>
          ))}
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-6">
          {tab === "overview" && (summary ? <KPICards kpis={summary.remediation} /> : <Loading />)}

          {tab === "control-gaps" && (summary ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 text-xs uppercase">
                  <th className="pb-2">Framework</th><th className="pb-2">Control</th>
                  <th className="pb-2 text-right">Coverage</th><th className="pb-2 text-right">Critical-Tier Gaps</th>
                </tr>
              </thead>
              <tbody>
                {summary.top_control_gaps.map((g) => (
                  <tr key={`${g.framework_code}-${g.control_ref}`} className="border-t border-slate-100">
                    <td className="py-1.5 text-slate-500">{g.framework_code}</td>
                    <td className="py-1.5">{g.control_ref} — {g.title}</td>
                    <td className="py-1.5 text-right">{g.vendors_covered}/{g.vendors_total} ({g.coverage_pct.toFixed(0)}%)</td>
                    <td className="py-1.5 text-right">
                      {g.critical_tier_gaps > 0 ? <span className="text-red-600 font-medium">{g.critical_tier_gaps}</span> : 0}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <Loading />)}

          {tab === "renewals" && (summary ? (
            summary.contract_renewals_due.length === 0 ? <p className="text-sm text-slate-400">No renewals due in the next 90 days.</p> : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-slate-400 text-xs uppercase">
                    <th className="pb-2">Vendor</th><th className="pb-2">Contract</th><th className="pb-2">Expires</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.contract_renewals_due.map((c) => (
                    <tr key={c.id} className="border-t border-slate-100">
                      <td className="py-1.5">{c.vendor_name}</td>
                      <td className="py-1.5 text-slate-600">{c.contract_name}</td>
                      <td className="py-1.5">{new Date(c.expiration_date).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )
          ) : <Loading />)}

          {tab === "playbooks" && (executions ? (
            executions.length === 0 ? <p className="text-sm text-slate-400">No playbooks have run yet.</p> : (
              <div className="space-y-2">
                {executions.map((e) => (
                  <div key={e.id} className="rounded-md border border-slate-200 p-3 text-sm">
                    <div className="flex justify-between">
                      <span className="font-medium">{e.playbook_name}</span>
                      <span className={e.status === "completed" ? "text-green-600" : "text-red-600"}>{e.status}</span>
                    </div>
                    <div className="text-xs text-slate-500">{e.vendor_name} · {new Date(e.started_at).toLocaleString()}</div>
                    <ul className="mt-1 text-xs text-slate-600 list-disc list-inside">
                      {e.step_log.map((s, i) => <li key={i}>{s.type}{s.error ? ` — error: ${s.error}` : ""}</li>)}
                    </ul>
                  </div>
                ))}
              </div>
            )
          ) : <Loading />)}

          {tab === "coverage" && <VendorCoveragePanel />}
        </div>
      </main>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: number; accent?: string }) {
  return (
    <div className="rounded-md bg-white border border-slate-200 p-3 text-center">
      <div className={`text-2xl font-semibold ${accent ?? "text-slate-900"}`}>{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}

function Loading() {
  return <p className="text-slate-400 text-sm">Loading...</p>;
}

export default function BoardDashboard() {
  return (
    <AdminGate probe={() => api.boardSummary()}>
      <BoardDashboardBody />
    </AdminGate>
  );
}
