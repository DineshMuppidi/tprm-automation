import type { VendorRiskEntry } from "../../lib/types";

function bandColor(score: number | null): string {
  if (score === null) return "bg-slate-200 text-slate-500";
  if (score < 40) return "bg-green-100 text-green-800";
  if (score <= 70) return "bg-amber-100 text-amber-800";
  return "bg-red-100 text-red-800";
}

export default function RiskScoreboard({ vendors }: { vendors: VendorRiskEntry[] }) {
  const sorted = [...vendors].sort((a, b) => (b.risk_score ?? -1) - (a.risk_score ?? -1));

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-slate-400 text-xs uppercase">
          <th className="pb-2">Vendor</th>
          <th className="pb-2">Tier</th>
          <th className="pb-2 text-right">Open Alerts</th>
          <th className="pb-2 text-right">Risk Score</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((v) => (
          <tr key={v.id} className="border-t border-slate-100">
            <td className="py-1.5">{v.legal_name}</td>
            <td className="py-1.5 text-slate-500">{v.tier.replace("tier_", "T").replace("_", " ")}</td>
            <td className="py-1.5 text-right">{v.open_alert_count > 0 ? v.open_alert_count : "—"}</td>
            <td className="py-1.5 text-right">
              <span className={`inline-block px-2 py-0.5 rounded-full font-medium ${bandColor(v.risk_score)}`}>
                {v.risk_score !== null ? v.risk_score.toFixed(0) : "Not assessed"}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
