import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import type { FrameworkCoverage, VendorOut } from "../../lib/types";

const FRAMEWORK_COLOR: Record<string, string> = {
  NIST_CSF_2: "bg-blue-500", SOC2: "bg-purple-500", ISO27001: "bg-teal-500", HIPAA: "bg-rose-500",
};

export default function VendorCoveragePanel() {
  const [vendors, setVendors] = useState<VendorOut[]>([]);
  const [selected, setSelected] = useState("");
  const [coverage, setCoverage] = useState<Record<string, FrameworkCoverage> | null>(null);

  useEffect(() => { api.adminListVendors().then(setVendors); }, []);

  useEffect(() => {
    if (!selected) { setCoverage(null); return; }
    api.vendorFrameworkCoverage(selected).then(setCoverage);
  }, [selected]);

  return (
    <div className="space-y-4">
      <select value={selected} onChange={(e) => setSelected(e.target.value)} className="rounded-md border border-slate-300 p-2 text-sm">
        <option value="">Select a vendor...</option>
        {vendors.map((v) => <option key={v.id} value={v.id}>{v.legal_name}</option>)}
      </select>

      {coverage && (
        <div className="space-y-3">
          <p className="text-xs text-slate-500">
            Coverage inferred from the vendor's latest completed assessment, credited across frameworks
            via the control-mapping graph — a NIST-framed answer can imply SOC 2 / ISO 27001 / HIPAA coverage too.
          </p>
          {Object.entries(coverage).map(([code, c]) => (
            <div key={code}>
              <div className="flex justify-between text-xs text-slate-500 mb-1">
                <span className="font-medium text-slate-700">{code}</span>
                <span>{c.covered} / {c.total} controls ({c.pct.toFixed(0)}%)</span>
              </div>
              <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                <div className={`h-full rounded-full ${FRAMEWORK_COLOR[code] ?? "bg-slate-400"}`} style={{ width: `${c.pct}%` }} />
              </div>
            </div>
          ))}
        </div>
      )}
      {selected && !coverage && <p className="text-sm text-slate-400">Loading...</p>}
    </div>
  );
}
