interface Props {
  score: number; // 0-100, higher = riskier (vendor_risk_score semantics)
  label?: string;
}

// Green (<40) / Yellow (40-70) / Red (>70) — same bands as the Phase 2
// monitoring dashboard spec, so a vendor's risk color means the same thing
// everywhere in the platform.
function bandColor(score: number): string {
  if (score < 40) return "#16a34a";
  if (score <= 70) return "#d97706";
  return "#dc2626";
}
function bandLabel(score: number): string {
  if (score < 40) return "Low";
  if (score <= 70) return "Medium";
  return "High";
}

export default function RiskGauge({ score, label = "Vendor Risk" }: Props) {
  const clamped = Math.max(0, Math.min(100, score));
  const angle = (clamped / 100) * 180; // semicircle gauge
  const color = bandColor(clamped);
  const radius = 80;
  const cx = 100;
  const cy = 100;
  const toXY = (deg: number) => {
    const rad = (Math.PI * (180 - deg)) / 180;
    return [cx + radius * Math.cos(rad), cy - radius * Math.sin(rad)];
  };
  const [ex, ey] = toXY(angle);
  const largeArc = angle > 180 ? 1 : 0;

  return (
    <div className="flex flex-col items-center">
      <svg width="200" height="120" viewBox="0 0 200 110">
        <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="#e2e8f0" strokeWidth="16" strokeLinecap="round" />
        <path
          d={`M 20 100 A 80 80 0 ${largeArc} 1 ${ex} ${ey}`}
          fill="none" stroke={color} strokeWidth="16" strokeLinecap="round"
        />
        <text x="100" y="90" textAnchor="middle" fontSize="28" fontWeight="700" fill="#0f172a">
          {clamped.toFixed(0)}
        </text>
      </svg>
      <div className="text-sm text-slate-500">{label}</div>
      <div className="text-sm font-semibold" style={{ color }}>{bandLabel(clamped)}</div>
    </div>
  );
}
