import { useEffect, useState } from "react";
import AdminGate from "../components/AdminGate";
import { api } from "../lib/api";
import type { ComplianceCheckResult, ContractOut, ObligationOut, VendorOut } from "../lib/types";

function AdminContractsBody() {
  const [vendors, setVendors] = useState<VendorOut[]>([]);
  const [selectedVendor, setSelectedVendor] = useState("");
  const [contracts, setContracts] = useState<ContractOut[]>([]);
  const [obligations, setObligations] = useState<Record<string, ObligationOut[]>>({});
  const [complianceResults, setComplianceResults] = useState<ComplianceCheckResult[] | null>(null);

  const [uploadForm, setUploadForm] = useState({ contract_name: "", effective_date: "", expiration_date: "" });
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => { api.adminListVendors().then(setVendors); }, []);

  function refreshContracts(vendorId: string) {
    api.listVendorContracts(vendorId).then(async (list) => {
      setContracts(list);
      const obligationsByContract: Record<string, ObligationOut[]> = {};
      for (const c of list) {
        obligationsByContract[c.id] = await api.listContractObligations(c.id);
      }
      setObligations(obligationsByContract);
    });
  }

  useEffect(() => {
    setComplianceResults(null);
    if (selectedVendor) refreshContracts(selectedVendor);
    else setContracts([]);
  }, [selectedVendor]);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !selectedVendor) return;
    setUploading(true);
    try {
      await api.uploadContract(selectedVendor, file, uploadForm.contract_name, uploadForm.effective_date, uploadForm.expiration_date || undefined);
      setUploadForm({ contract_name: "", effective_date: "", expiration_date: "" });
      setFile(null);
      refreshContracts(selectedVendor);
    } finally {
      setUploading(false);
    }
  }

  async function handleCheckCompliance() {
    const results = await api.checkContractCompliance(selectedVendor);
    setComplianceResults(results);
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-4">
          <span className="font-semibold text-slate-900">TPRM Contracts</span>
          <a href="/admin/board" className="text-sm text-blue-600 hover:underline">Board reporting →</a>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8 space-y-6">
        <select value={selectedVendor} onChange={(e) => setSelectedVendor(e.target.value)} className="rounded-md border border-slate-300 p-2 text-sm">
          <option value="">Select a vendor...</option>
          {vendors.map((v) => <option key={v.id} value={v.id}>{v.legal_name}</option>)}
        </select>

        {selectedVendor && (
          <>
            <section className="bg-white rounded-lg border border-slate-200 p-6">
              <h2 className="text-sm font-semibold text-slate-700 mb-3">Upload Contract</h2>
              <form onSubmit={handleUpload} className="grid grid-cols-2 gap-3">
                <input
                  required placeholder="Contract name" value={uploadForm.contract_name}
                  onChange={(e) => setUploadForm({ ...uploadForm, contract_name: e.target.value })}
                  className="rounded-md border border-slate-300 p-2 text-sm col-span-2"
                />
                <label className="text-xs text-slate-500 col-span-2 -mb-2">Effective date</label>
                <input
                  required type="date" value={uploadForm.effective_date}
                  onChange={(e) => setUploadForm({ ...uploadForm, effective_date: e.target.value })}
                  className="rounded-md border border-slate-300 p-2 text-sm"
                />
                <input
                  type="date" placeholder="Expiration date (optional)" value={uploadForm.expiration_date}
                  onChange={(e) => setUploadForm({ ...uploadForm, expiration_date: e.target.value })}
                  className="rounded-md border border-slate-300 p-2 text-sm"
                />
                <input
                  required type="file" accept=".txt,.pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  className="col-span-2 text-sm"
                />
                <button disabled={uploading} className="col-span-2 rounded-md bg-blue-600 text-white text-sm font-medium py-2 hover:bg-blue-700 disabled:opacity-50">
                  {uploading ? "Parsing contract..." : "Upload & extract terms"}
                </button>
              </form>
            </section>

            <section className="bg-white rounded-lg border border-slate-200 p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-700">Contracts</h2>
                <button onClick={handleCheckCompliance} className="text-sm text-blue-600 hover:underline">
                  Check compliance →
                </button>
              </div>

              {complianceResults && (
                <div className="space-y-1">
                  {complianceResults.length === 0 && <p className="text-xs text-slate-400">No certification obligations to check.</p>}
                  {complianceResults.map((r) => (
                    <div key={r.obligation_id} className={`text-xs rounded p-2 ${r.status === "compliant" ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"}`}>
                      <span className="font-medium">{r.status}</span> — {r.reason}
                    </div>
                  ))}
                </div>
              )}

              {contracts.length === 0 && <p className="text-sm text-slate-400">No contracts on file for this vendor.</p>}
              {contracts.map((c) => (
                <div key={c.id} className="rounded-md border border-slate-200 p-3">
                  <div className="flex justify-between items-center">
                    <span className="font-medium text-sm">{c.contract_name}</span>
                    <span className="text-xs text-slate-500">
                      {c.effective_date} → {c.expiration_date ?? "no end date"} {c.auto_renews && "(auto-renews)"}
                    </span>
                  </div>
                  {c.extracted_terms && (
                    <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-600">
                      {c.extracted_terms.sla_uptime_pct != null && <><dt className="text-slate-400">Uptime SLA</dt><dd>{String(c.extracted_terms.sla_uptime_pct)}%</dd></>}
                      {c.extracted_terms.incident_notification_sla_hours != null && <><dt className="text-slate-400">Breach notification</dt><dd>{String(c.extracted_terms.incident_notification_sla_hours)}h</dd></>}
                      {c.extracted_terms.termination_notice_days != null && <><dt className="text-slate-400">Termination notice</dt><dd>{String(c.extracted_terms.termination_notice_days)} days</dd></>}
                    </dl>
                  )}
                  {obligations[c.id]?.length > 0 && (
                    <div className="mt-2">
                      <p className="text-xs text-slate-400 mb-1">Obligations</p>
                      <ul className="text-xs text-slate-600 space-y-0.5">
                        {obligations[c.id].map((o) => (
                          <li key={o.id}>
                            <span className="text-slate-400">[{o.obligation_type}]</span> {o.description}
                            {o.last_check_status && <span className={o.last_check_status === "compliant" ? "text-green-600" : "text-red-600"}> — {o.last_check_status}</span>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </section>
          </>
        )}
      </main>
    </div>
  );
}

export default function AdminContracts() {
  return (
    <AdminGate probe={() => api.adminListVendors()}>
      <AdminContractsBody />
    </AdminGate>
  );
}
