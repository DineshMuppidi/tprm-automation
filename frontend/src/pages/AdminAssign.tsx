import { useEffect, useState } from "react";
import AdminGate from "../components/AdminGate";
import TemplateSelector from "../components/TemplateSelector";
import { api, ApiError } from "../lib/api";
import type { AssessmentSummary, TemplateOut, VendorOut } from "../lib/types";

const TIERS = [
  { value: "tier_1_critical", label: "Tier 1 — Critical" },
  { value: "tier_2_high", label: "Tier 2 — High" },
  { value: "tier_3_medium", label: "Tier 3 — Medium" },
  { value: "tier_4_low", label: "Tier 4 — Low" },
];
const DATA_ACCESS_LEVELS = ["none", "internal_only", "confidential", "restricted_pii", "phi"];

function AdminAssignBody() {
  const [error, setError] = useState("");

  const [vendors, setVendors] = useState<VendorOut[]>([]);
  const [templates, setTemplates] = useState<TemplateOut[]>([]);
  const [assessments, setAssessments] = useState<AssessmentSummary[]>([]);

  const [selectedVendor, setSelectedVendor] = useState("");
  const [selectedTemplate, setSelectedTemplate] = useState("");
  const [assignResult, setAssignResult] = useState<(AssessmentSummary & { dev_login_url?: string | null }) | null>(null);

  const [showNewVendor, setShowNewVendor] = useState(false);
  const [newVendor, setNewVendor] = useState({
    legal_name: "", industry: "", tier: "tier_2_high", data_access_level: "confidential",
    contact_name: "", contact_email: "", contact_role: "",
  });

  function refresh() {
    Promise.all([api.adminListVendors(), api.adminListTemplates(), api.adminListAssessments()])
      .then(([v, t, a]) => { setVendors(v); setTemplates(t); setAssessments(a); })
      .catch(() => setError("Failed to load admin data."));
  }

  useEffect(refresh, []);

  async function handleCreateVendor(e: React.FormEvent) {
    e.preventDefault();
    await api.adminCreateVendor({
      legal_name: newVendor.legal_name, industry: newVendor.industry, tier: newVendor.tier,
      data_access_level: newVendor.data_access_level,
      primary_contact: { full_name: newVendor.contact_name, email: newVendor.contact_email, role: newVendor.contact_role },
    });
    setShowNewVendor(false);
    setNewVendor({ legal_name: "", industry: "", tier: "tier_2_high", data_access_level: "confidential", contact_name: "", contact_email: "", contact_role: "" });
    refresh();
  }

  async function handleAssign() {
    if (!selectedVendor || !selectedTemplate) return;
    try {
      const result = await api.adminAssignAssessment(selectedVendor, selectedTemplate);
      setAssignResult(result);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.message) : "Failed to assign assessment.");
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-4">
          <span className="font-semibold text-slate-900">TPRM Admin — Assign Assessments</span>
          <a href="/admin/monitoring" className="text-sm text-blue-600 hover:underline">Monitoring dashboard →</a>
        </div>
      </header>
      <main className="max-w-4xl mx-auto px-4 py-8 space-y-8">
        <section className="bg-white rounded-lg border border-slate-200 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-700">Assign a Questionnaire</h2>
            <button onClick={() => setShowNewVendor((s) => !s)} className="text-sm text-blue-600 hover:underline">
              {showNewVendor ? "Cancel" : "+ New vendor"}
            </button>
          </div>

          {showNewVendor && (
            <form onSubmit={handleCreateVendor} className="grid grid-cols-2 gap-3 bg-slate-50 rounded-md p-4 border border-slate-200">
              <input required placeholder="Legal name" value={newVendor.legal_name}
                     onChange={(e) => setNewVendor({ ...newVendor, legal_name: e.target.value })}
                     className="rounded-md border border-slate-300 p-2 text-sm col-span-2" />
              <input placeholder="Industry" value={newVendor.industry}
                     onChange={(e) => setNewVendor({ ...newVendor, industry: e.target.value })}
                     className="rounded-md border border-slate-300 p-2 text-sm" />
              <select value={newVendor.tier} onChange={(e) => setNewVendor({ ...newVendor, tier: e.target.value })}
                      className="rounded-md border border-slate-300 p-2 text-sm">
                {TIERS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
              <select value={newVendor.data_access_level} onChange={(e) => setNewVendor({ ...newVendor, data_access_level: e.target.value })}
                      className="rounded-md border border-slate-300 p-2 text-sm col-span-2">
                {DATA_ACCESS_LEVELS.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
              <input required placeholder="Primary contact name" value={newVendor.contact_name}
                     onChange={(e) => setNewVendor({ ...newVendor, contact_name: e.target.value })}
                     className="rounded-md border border-slate-300 p-2 text-sm" />
              <input required type="email" placeholder="Primary contact email" value={newVendor.contact_email}
                     onChange={(e) => setNewVendor({ ...newVendor, contact_email: e.target.value })}
                     className="rounded-md border border-slate-300 p-2 text-sm" />
              <button className="col-span-2 rounded-md bg-blue-600 text-white text-sm font-medium py-2 hover:bg-blue-700">
                Create vendor
              </button>
            </form>
          )}

          <div className="grid grid-cols-2 gap-3">
            <select value={selectedVendor} onChange={(e) => setSelectedVendor(e.target.value)}
                    className="rounded-md border border-slate-300 p-2 text-sm">
              <option value="">Select a vendor...</option>
              {vendors.map((v) => <option key={v.id} value={v.id}>{v.legal_name} ({v.tier})</option>)}
            </select>
            <TemplateSelector templates={templates} value={selectedTemplate} onChange={setSelectedTemplate} />
          </div>
          <button
            onClick={handleAssign}
            disabled={!selectedVendor || !selectedTemplate}
            className="rounded-md bg-blue-600 text-white text-sm font-medium px-4 py-2 hover:bg-blue-700 disabled:opacity-50"
          >
            Assign assessment
          </button>
          {error && <p className="text-sm text-red-600">{error}</p>}

          {assignResult && (
            <div className="rounded-md bg-green-50 border border-green-200 p-3 text-sm text-green-800">
              Assigned "{assignResult.template_name}" to {assignResult.vendor_name}.
              {assignResult.dev_login_url && (
                <>
                  {" "}
                  <a href={assignResult.dev_login_url} target="_blank" rel="noreferrer" className="underline">
                    Open vendor login link (dev only — real email would be sent instead)
                  </a>
                </>
              )}
            </div>
          )}
        </section>

        <section className="bg-white rounded-lg border border-slate-200 p-6">
          <h2 className="text-sm font-semibold text-slate-700 mb-3">All Assessments</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 text-xs uppercase">
                <th className="pb-2">Vendor</th><th className="pb-2">Template</th>
                <th className="pb-2">Status</th><th className="pb-2 text-right">Progress</th>
                <th className="pb-2 text-right">Score</th>
              </tr>
            </thead>
            <tbody>
              {assessments.map((a) => (
                <tr key={a.id} className="border-t border-slate-100">
                  <td className="py-1.5">{a.vendor_name}</td>
                  <td className="py-1.5 text-slate-500">{a.template_name}</td>
                  <td className="py-1.5">{a.status}</td>
                  <td className="py-1.5 text-right">{a.progress_pct.toFixed(0)}%</td>
                  <td className="py-1.5 text-right">{a.overall_score?.toFixed(0) ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </main>
    </div>
  );
}

export default function AdminAssign() {
  return (
    <AdminGate probe={() => api.adminListVendors()}>
      <AdminAssignBody />
    </AdminGate>
  );
}
