import { useEffect, useState } from "react";
import AdminGate from "../components/AdminGate";
import AlertFeed from "../components/monitoring/AlertFeed";
import MonitoringStatusPanel from "../components/monitoring/MonitoringStatusPanel";
import RiskScoreboard from "../components/monitoring/RiskScoreboard";
import { api } from "../lib/api";
import type { AlertOut, MonitoringStatusOut, RunChecksOut, VendorRiskEntry } from "../lib/types";

type Tab = "alerts" | "scoreboard" | "status";

function DashboardBody() {
  const [tab, setTab] = useState<Tab>("alerts");
  const [alerts, setAlerts] = useState<AlertOut[] | null>(null);
  const [vendors, setVendors] = useState<VendorRiskEntry[] | null>(null);
  const [status, setStatus] = useState<MonitoringStatusOut | null>(null);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<RunChecksOut | null>(null);

  function refresh() {
    api.listAlerts().then(setAlerts);
    api.riskScoreboard().then(setVendors);
    api.monitoringStatus().then(setStatus);
  }

  useEffect(refresh, []);

  async function handleRunChecks() {
    setRunning(true);
    setRunResult(null);
    try {
      const result = await api.runMonitoringChecks();
      setRunResult(result);
      refresh();
    } finally {
      setRunning(false);
    }
  }

  const openCritical = alerts?.filter((a) => a.severity === "critical" && (a.status === "new" || a.status === "escalated")).length ?? 0;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="font-semibold text-slate-900">TPRM Monitoring</span>
            <a href="/admin" className="text-sm text-blue-600 hover:underline">Assign assessments →</a>
            <a href="/admin/findings" className="text-sm text-blue-600 hover:underline">Findings & remediation →</a>
            <a href="/admin/board" className="text-sm text-blue-600 hover:underline">Board reporting →</a>
          </div>
          <div className="flex items-center gap-3">
            {openCritical > 0 && (
              <span className="text-xs font-semibold text-red-700 bg-red-100 rounded-full px-2 py-1">
                {openCritical} critical open
              </span>
            )}
            <button
              onClick={handleRunChecks} disabled={running}
              className="rounded-md bg-blue-600 text-white text-sm font-medium px-3 py-1.5 hover:bg-blue-700 disabled:opacity-60"
            >
              {running ? "Running checks..." : "Run checks now"}
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6 space-y-4">
        {runResult && (
          <div className="rounded-md bg-blue-50 border border-blue-200 p-3 text-sm text-blue-800">
            Checks complete: {runResult.cert_expiry} cert, {runResult.breach_cve} breach/CVE, {runResult.news} news,{" "}
            {runResult.financial} financial alert(s) created; {runResult.escalations} alert(s) escalated.
          </div>
        )}

        <div className="flex gap-1 border-b border-slate-200">
          {(["alerts", "scoreboard", "status"] as Tab[]).map((t) => (
            <button
              key={t} onClick={() => setTab(t)}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
                tab === t ? "border-blue-600 text-blue-600" : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              {t === "alerts" ? "Alert Feed" : t === "scoreboard" ? "Vendor Risk Scoreboard" : "Monitoring Status"}
            </button>
          ))}
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-6">
          {tab === "alerts" && (alerts ? <AlertFeed alerts={alerts} onChanged={refresh} /> : <Loading />)}
          {tab === "scoreboard" && (vendors ? <RiskScoreboard vendors={vendors} /> : <Loading />)}
          {tab === "status" && (status ? <MonitoringStatusPanel status={status} /> : <Loading />)}
        </div>
      </main>
    </div>
  );
}

function Loading() {
  return <p className="text-slate-400 text-sm">Loading...</p>;
}

export default function MonitoringDashboard() {
  return (
    <AdminGate probe={() => api.monitoringStatus()}>
      <DashboardBody />
    </AdminGate>
  );
}
