import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import Header from "../components/Header";
import RiskGauge from "../components/RiskGauge";
import { api, BASE_URL, getSession } from "../lib/api";
import type { AssessmentDetail, RiskBreakdown } from "../lib/types";

export default function Result() {
  const { id = "" } = useParams();
  const [detail, setDetail] = useState<AssessmentDetail | null>(null);
  const [risk, setRisk] = useState<RiskBreakdown | null>(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    api.getAssessment(id).then(setDetail);
    api.getRisk(id).then(setRisk);
  }, [id]);

  async function handleDownload() {
    setDownloading(true);
    try {
      const blob = await fetch(`${BASE_URL}/assessments/${id}/report`, {
        headers: { Authorization: `Bearer ${getSession()?.access_token ?? ""}` },
      }).then((r) => r.blob());
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
    } finally {
      setDownloading(false);
    }
  }

  if (!detail || !risk) {
    return (
      <div className="min-h-screen bg-slate-50">
        <Header />
        <p className="text-center text-slate-400 mt-12 text-sm">Loading...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <Header />
      <main className="max-w-3xl mx-auto px-4 py-8 space-y-6">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">{detail.template_name} — Results</h1>
          <p className="text-sm text-slate-500">{detail.vendor_name}</p>
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-6 flex flex-wrap items-center justify-around gap-6">
          <RiskGauge score={risk.vendor_risk_score} label="Vendor Risk Exposure" />
          <div className="text-center">
            <div className="text-3xl font-bold text-slate-900">{risk.overall_score.toFixed(0)}/100</div>
            <div className="text-sm text-slate-500">Compliance Strength Score</div>
          </div>
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-6">
          <h2 className="text-sm font-semibold text-slate-700 mb-3">Response Breakdown</h2>
          <div className="flex flex-wrap gap-3">
            {Object.entries(risk.classification_counts).map(([classification, count]) => (
              <div key={classification} className="rounded-md bg-slate-50 border border-slate-200 px-3 py-2 text-sm">
                <span className="font-semibold">{count}</span>{" "}
                <span className="text-slate-500 capitalize">{classification}</span>
              </div>
            ))}
          </div>
        </div>

        {risk.control_scores.length > 0 && (
          <div className="bg-white rounded-lg border border-slate-200 p-6">
            <h2 className="text-sm font-semibold text-slate-700 mb-3">Control Coverage</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 text-xs uppercase">
                  <th className="pb-2">Framework</th>
                  <th className="pb-2">Control</th>
                  <th className="pb-2 text-right">Score</th>
                </tr>
              </thead>
              <tbody>
                {risk.control_scores.map((c) => (
                  <tr key={c.control_id} className="border-t border-slate-100">
                    <td className="py-1.5 text-slate-500">{c.framework_code}</td>
                    <td className="py-1.5">{c.control_ref} — {c.control_title}</td>
                    <td className="py-1.5 text-right font-medium">{c.score.toFixed(0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <button
          onClick={handleDownload}
          disabled={downloading}
          className="rounded-md bg-blue-600 text-white text-sm font-medium px-4 py-2 hover:bg-blue-700 disabled:opacity-60"
        >
          {downloading ? "Preparing report..." : "Download PDF report"}
        </button>
      </main>
    </div>
  );
}
