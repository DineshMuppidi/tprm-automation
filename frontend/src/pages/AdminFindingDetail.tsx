import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import AdminGate from "../components/AdminGate";
import CommentThread from "../components/finding/CommentThread";
import FindingInfoPanel from "../components/finding/FindingInfoPanel";
import { api } from "../lib/api";
import type { FindingDetail } from "../lib/types";

function AdminFindingDetailBody() {
  const { id = "" } = useParams();
  const [finding, setFinding] = useState<FindingDetail | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => { api.adminGetFinding(id).then(setFinding); }, [id]);
  useEffect(load, [load]);

  if (!finding) return <p className="text-center text-slate-400 mt-12 text-sm">Loading...</p>;

  const isResolved = ["closed", "exception_granted"].includes(finding.status);

  async function handleClose() {
    setBusy(true);
    try { await api.adminCloseFinding(id, note); setNote(""); load(); } finally { setBusy(false); }
  }
  async function handleReject() {
    if (!note.trim()) return;
    setBusy(true);
    try { await api.adminRejectFinding(id, note); setNote(""); load(); } finally { setBusy(false); }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="max-w-2xl mx-auto px-4 py-3">
          <a href="/admin/findings" className="text-sm text-blue-600 hover:underline">← All findings</a>
        </div>
      </header>
      <main className="max-w-2xl mx-auto px-4 py-8 space-y-4">
        <FindingInfoPanel finding={finding} />

        {!isResolved && (
          <div className="bg-white rounded-lg border border-slate-200 p-5 space-y-2">
            <h2 className="text-sm font-semibold text-slate-700">Reviewer Actions</h2>
            <textarea
              value={note} onChange={(e) => setNote(e.target.value)} rows={2}
              placeholder="Note (required to reject; optional to close)..."
              className="w-full rounded-md border border-slate-300 p-2 text-sm"
            />
            <div className="flex gap-2">
              <button onClick={handleClose} disabled={busy} className="rounded-md bg-green-600 text-white text-sm px-3 py-1.5 hover:bg-green-700 disabled:opacity-50">
                Close finding
              </button>
              <button onClick={handleReject} disabled={busy || !note.trim()} className="rounded-md bg-amber-600 text-white text-sm px-3 py-1.5 hover:bg-amber-700 disabled:opacity-50">
                Send back for revision
              </button>
            </div>
          </div>
        )}

        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-3">Messages</h2>
          <CommentThread comments={finding.comments} onSend={async (body) => { await api.addFindingComment(id, body, true); load(); }} />
        </div>
      </main>
    </div>
  );
}

export default function AdminFindingDetail() {
  return (
    <AdminGate probe={() => api.kpiReport()}>
      <AdminFindingDetailBody />
    </AdminGate>
  );
}
