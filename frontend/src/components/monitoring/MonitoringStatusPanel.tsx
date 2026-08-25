import type { MonitoringStatusOut } from "../../lib/types";

export default function MonitoringStatusPanel({ status }: { status: MonitoringStatusOut }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-3">
        <Stat label="Alerts (7d)" value={status.stats.alerts_this_week} />
        <Stat label="Escalated (7d)" value={status.stats.escalated_this_week} />
        <Stat label="Resolved (7d)" value={status.stats.resolved_this_week} />
        <Stat
          label="Avg time to ack"
          value={status.stats.avg_ack_minutes !== null ? `${status.stats.avg_ack_minutes.toFixed(0)}m` : "—"}
        />
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-400 text-xs uppercase">
            <th className="pb-2">Data Source</th>
            <th className="pb-2">Last Checked</th>
            <th className="pb-2">Status</th>
          </tr>
        </thead>
        <tbody>
          {status.sources.map((s) => (
            <tr key={s.code} className="border-t border-slate-100">
              <td className="py-1.5">{s.name}</td>
              <td className="py-1.5 text-slate-500">
                {s.last_checked_at ? new Date(s.last_checked_at).toLocaleString() : "Never run"}
              </td>
              <td className="py-1.5">
                {s.last_error ? (
                  <span className="text-red-600">⚠ {s.last_error}</span>
                ) : s.last_success_at ? (
                  <span className="text-green-600">✓ Healthy</span>
                ) : (
                  <span className="text-slate-400">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md bg-slate-50 border border-slate-200 p-3 text-center">
      <div className="text-xl font-semibold text-slate-900">{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}
