import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../components/Header";
import { FindingStatusBadge, SeverityBadge } from "../components/finding/StatusBadge";
import { api } from "../lib/api";
import type { FindingSummary } from "../lib/types";

export default function FindingsList() {
  const [findings, setFindings] = useState<FindingSummary[] | null>(null);
  const navigate = useNavigate();

  useEffect(() => { api.myFindings().then(setFindings); }, []);

  const open = findings?.filter((f) => !["closed", "exception_granted"].includes(f.status)) ?? [];
  const closed = findings?.filter((f) => ["closed", "exception_granted"].includes(f.status)) ?? [];

  return (
    <div className="min-h-screen bg-slate-50">
      <Header />
      <main className="max-w-4xl mx-auto px-4 py-8">
        <h1 className="text-lg font-semibold text-slate-900 mb-1">Findings</h1>
        <p className="text-sm text-slate-500 mb-6">
          Security and compliance gaps that need remediation. Each has a deadline based on severity.
        </p>

        {findings === null && <p className="text-slate-400 text-sm">Loading...</p>}
        {findings?.length === 0 && <p className="text-slate-400 text-sm">No findings assigned.</p>}

        {open.length > 0 && (
          <div className="space-y-2 mb-8">
            {open.map((f) => (
              <FindingRow key={f.id} f={f} onClick={() => navigate(`/findings/${f.id}`)} />
            ))}
          </div>
        )}

        {closed.length > 0 && (
          <>
            <h2 className="text-sm font-semibold text-slate-500 mb-2">Resolved</h2>
            <div className="space-y-2 opacity-70">
              {closed.map((f) => (
                <FindingRow key={f.id} f={f} onClick={() => navigate(`/findings/${f.id}`)} />
              ))}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function FindingRow({ f, onClick }: { f: FindingSummary; onClick: () => void }) {
  return (
    <button onClick={onClick} className="w-full text-left bg-white rounded-lg border border-slate-200 p-4 hover:border-blue-400 transition">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <SeverityBadge severity={f.severity} />
            <FindingStatusBadge status={f.status} />
          </div>
          <p className="font-medium text-slate-900">{f.title}</p>
        </div>
        <span className="text-xs text-slate-500 shrink-0">Due {new Date(f.due_at).toLocaleDateString()}</span>
      </div>
    </button>
  );
}
