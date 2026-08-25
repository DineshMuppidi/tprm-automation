import { useState } from "react";
import { api } from "../../lib/api";
import type { AlertOut, AlertSeverity, AlertStatus } from "../../lib/types";

const SEVERITY_STYLE: Record<AlertSeverity, string> = {
  critical: "border-l-4 border-red-600 bg-red-50",
  high: "border-l-4 border-orange-500 bg-orange-50",
  medium: "border-l-4 border-amber-400 bg-amber-50",
  low: "border-l-4 border-slate-300 bg-slate-50",
};

const STATUS_LABEL: Record<AlertStatus, string> = {
  new: "New", acknowledged: "Acknowledged", escalated: "Escalated", resolved: "Resolved", suppressed: "Suppressed",
};

interface Props {
  alerts: AlertOut[];
  onChanged: () => void;
}

export default function AlertFeed({ alerts, onChanged }: Props) {
  const [severityFilter, setSeverityFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [query, setQuery] = useState("");
  const [suppressingId, setSuppressingId] = useState<string | null>(null);
  const [suppressReason, setSuppressReason] = useState("");

  const filtered = alerts.filter((a) => {
    if (severityFilter && a.severity !== severityFilter) return false;
    if (statusFilter && a.status !== statusFilter) return false;
    if (query && !`${a.title} ${a.vendor_name}`.toLowerCase().includes(query.toLowerCase())) return false;
    return true;
  });

  async function handleAcknowledge(id: string) {
    await api.acknowledgeAlert(id);
    onChanged();
  }
  async function handleResolve(id: string) {
    await api.resolveAlert(id);
    onChanged();
  }
  async function handleSuppress(id: string) {
    if (!suppressReason.trim()) return;
    await api.suppressAlert(id, suppressReason);
    setSuppressingId(null);
    setSuppressReason("");
    onChanged();
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <input
          placeholder="Search alerts..." value={query} onChange={(e) => setQuery(e.target.value)}
          className="rounded-md border border-slate-300 p-1.5 text-sm flex-1 min-w-[160px]"
        />
        <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)} className="rounded-md border border-slate-300 p-1.5 text-sm">
          <option value="">All severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-md border border-slate-300 p-1.5 text-sm">
          <option value="">All statuses</option>
          <option value="new">New</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="escalated">Escalated</option>
          <option value="resolved">Resolved</option>
          <option value="suppressed">Suppressed</option>
        </select>
      </div>

      {filtered.length === 0 && <p className="text-sm text-slate-400">No alerts match.</p>}

      <div className="space-y-2">
        {filtered.map((a) => (
          <div key={a.id} className={`rounded-md p-3 ${SEVERITY_STYLE[a.severity]}`}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-slate-500">
                  <span className="font-semibold">{a.severity}</span>
                  <span>· {a.alert_type.replace("_", " ")}</span>
                  <span>· {STATUS_LABEL[a.status]}</span>
                </div>
                <p className="font-medium text-slate-900 mt-0.5">{a.title}</p>
                <p className="text-xs text-slate-500">{a.vendor_name} · {new Date(a.detected_at).toLocaleString()}</p>
              </div>
              {a.risk_score_delta ? (
                <span className="shrink-0 text-xs font-semibold text-red-700">+{a.risk_score_delta.toFixed(0)} risk</span>
              ) : null}
            </div>

            {(a.status === "new" || a.status === "escalated") && (
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                <button onClick={() => handleAcknowledge(a.id)} className="rounded bg-white border border-slate-300 px-2 py-1 hover:border-blue-400">
                  Acknowledge
                </button>
                <button onClick={() => handleResolve(a.id)} className="rounded bg-white border border-slate-300 px-2 py-1 hover:border-blue-400">
                  Resolve
                </button>
                {suppressingId === a.id ? (
                  <>
                    <input
                      autoFocus placeholder="Suppression reason..." value={suppressReason}
                      onChange={(e) => setSuppressReason(e.target.value)}
                      className="rounded border border-slate-300 px-2 py-1"
                    />
                    <button onClick={() => handleSuppress(a.id)} className="rounded bg-slate-700 text-white px-2 py-1">Confirm</button>
                    <button onClick={() => setSuppressingId(null)} className="text-slate-400">Cancel</button>
                  </>
                ) : (
                  <button onClick={() => setSuppressingId(a.id)} className="rounded bg-white border border-slate-300 px-2 py-1 hover:border-blue-400">
                    Suppress
                  </button>
                )}
              </div>
            )}
            {a.status === "acknowledged" && (
              <div className="mt-2">
                <button onClick={() => handleResolve(a.id)} className="rounded bg-white border border-slate-300 px-2 py-1 text-xs hover:border-blue-400">
                  Resolve
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
