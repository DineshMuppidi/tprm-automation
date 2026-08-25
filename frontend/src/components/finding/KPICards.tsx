import type { KPIReport } from "../../lib/types";

export default function KPICards({ kpis }: { kpis: KPIReport }) {
  const v = kpis.remediation_velocity;
  const closedCount = v.by_status.closed ?? 0;
  const totalCount = Object.values(v.by_status).reduce((a, b) => a + b, 0);

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <Card label="Findings Closed / Total" value={`${closedCount} / ${totalCount}`} />
      <Card label="Mean Time to Resolution" value={v.mttr_days !== null ? `${v.mttr_days.toFixed(1)}d` : "—"} />
      <Card label="Closed (30d)" value={v.closed_last_30_days} />
      <Card label="Rework Rate" value={`${kpis.quality.rework_rate_pct.toFixed(0)}%`} />
      <Card label="Exception Rate" value={`${kpis.quality.exception_rate_pct.toFixed(0)}%`} />
      <Card label="Avg Vendor Risk" value={kpis.risk_and_regulatory.avg_vendor_risk_score?.toFixed(0) ?? "—"} />
      <Card label="Evidence Coverage" value={`${kpis.risk_and_regulatory.evidence_coverage_pct.toFixed(0)}%`} />
      <Card
        label="Risk Bands (L/M/H)"
        value={`${kpis.risk_and_regulatory.vendor_risk_band_counts.low}/${kpis.risk_and_regulatory.vendor_risk_band_counts.medium}/${kpis.risk_and_regulatory.vendor_risk_band_counts.high}`}
      />
    </div>
  );
}

function Card({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md bg-white border border-slate-200 p-3 text-center">
      <div className="text-lg font-semibold text-slate-900">{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}
