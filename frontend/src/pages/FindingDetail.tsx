import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import Header from "../components/Header";
import EvidenceUpload from "../components/EvidenceUpload";
import CommentThread from "../components/finding/CommentThread";
import EscalationNotification from "../components/finding/EscalationNotification";
import FindingInfoPanel from "../components/finding/FindingInfoPanel";
import { api } from "../lib/api";
import type { FindingDetail as FindingDetailType } from "../lib/types";

export default function FindingDetail() {
  const { id = "" } = useParams();
  const [finding, setFinding] = useState<FindingDetailType | null>(null);
  const [planText, setPlanText] = useState("");
  const [submittingPlan, setSubmittingPlan] = useState(false);
  const [submittingEvidence, setSubmittingEvidence] = useState(false);
  const [showException, setShowException] = useState(false);
  const [exceptionForm, setExceptionForm] = useState({ justification: "", compensating_controls: "" });

  const load = useCallback(() => {
    api.getFinding(id).then((f) => {
      setFinding(f);
      setPlanText((prev) => prev || f.remediation_plan || "");
    });
  }, [id]);

  useEffect(load, [load]);

  if (!finding) {
    return (
      <div className="min-h-screen bg-slate-50">
        <Header />
        <p className="text-center text-slate-400 mt-12 text-sm">Loading...</p>
      </div>
    );
  }

  const canAcknowledge = finding.status === "new";
  const canEditPlan = ["assigned", "in_progress", "rejected"].includes(finding.status);
  const canManageEvidence = finding.remediation_plan && ["in_progress", "rejected"].includes(finding.status);
  const isResolved = ["closed", "exception_granted"].includes(finding.status);

  async function handleAcknowledge() {
    await api.acknowledgeFinding(id);
    load();
  }

  async function handleSubmitPlan() {
    if (!planText.trim()) return;
    setSubmittingPlan(true);
    try {
      await api.submitPlan(id, planText);
      load();
    } finally {
      setSubmittingPlan(false);
    }
  }

  async function handleSubmitForValidation() {
    setSubmittingEvidence(true);
    try {
      await api.submitFinding(id);
      load();
    } finally {
      setSubmittingEvidence(false);
    }
  }

  async function handleRequestException() {
    await api.requestException(id, exceptionForm.justification, exceptionForm.compensating_controls);
    setShowException(false);
    load();
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <Header />
      <main className="max-w-2xl mx-auto px-4 py-8 space-y-4">
        <EscalationNotification finding={finding} />
        <FindingInfoPanel finding={finding} />

        {canAcknowledge && (
          <button onClick={handleAcknowledge} className="rounded-md bg-blue-600 text-white text-sm font-medium px-4 py-2 hover:bg-blue-700">
            Acknowledge finding
          </button>
        )}

        {canEditPlan && (
          <div className="bg-white rounded-lg border border-slate-200 p-5 space-y-2">
            <h2 className="text-sm font-semibold text-slate-700">Remediation Plan</h2>
            <textarea
              value={planText} onChange={(e) => setPlanText(e.target.value)} rows={4}
              placeholder="Describe the concrete steps and timeline for fixing this..."
              className="w-full rounded-md border border-slate-300 p-2 text-sm"
            />
            <button
              onClick={handleSubmitPlan} disabled={submittingPlan || !planText.trim()}
              className="rounded-md bg-blue-600 text-white text-sm font-medium px-4 py-2 hover:bg-blue-700 disabled:opacity-50"
            >
              {submittingPlan ? "Submitting..." : "Submit plan"}
            </button>
          </div>
        )}

        {canManageEvidence && (
          <div className="bg-white rounded-lg border border-slate-200 p-5 space-y-3">
            <h2 className="text-sm font-semibold text-slate-700">Evidence</h2>
            <EvidenceUpload
              evidence={finding.evidence}
              readOnly={false}
              onUpload={async (file) => { await api.uploadFindingEvidence(id, file); load(); }}
            />
            <button
              onClick={handleSubmitForValidation} disabled={submittingEvidence || finding.evidence.length === 0}
              className="rounded-md bg-blue-600 text-white text-sm font-medium px-4 py-2 hover:bg-blue-700 disabled:opacity-50"
            >
              {submittingEvidence ? "Submitting..." : "Submit for validation"}
            </button>
          </div>
        )}

        {!isResolved && (
          <div className="bg-white rounded-lg border border-slate-200 p-5">
            {showException ? (
              <div className="space-y-2">
                <h2 className="text-sm font-semibold text-slate-700">Request an Exception</h2>
                <textarea
                  placeholder="Why can't this be remediated? (e.g. legacy system constraints)"
                  value={exceptionForm.justification}
                  onChange={(e) => setExceptionForm({ ...exceptionForm, justification: e.target.value })}
                  rows={2} className="w-full rounded-md border border-slate-300 p-2 text-sm"
                />
                <textarea
                  placeholder="What compensating controls reduce the risk in the meantime?"
                  value={exceptionForm.compensating_controls}
                  onChange={(e) => setExceptionForm({ ...exceptionForm, compensating_controls: e.target.value })}
                  rows={2} className="w-full rounded-md border border-slate-300 p-2 text-sm"
                />
                <div className="flex gap-2">
                  <button onClick={handleRequestException} disabled={!exceptionForm.justification.trim()} className="rounded-md bg-slate-700 text-white text-sm px-3 py-1.5 disabled:opacity-50">
                    Submit request
                  </button>
                  <button onClick={() => setShowException(false)} className="text-sm text-slate-400">Cancel</button>
                </div>
              </div>
            ) : (
              <button onClick={() => setShowException(true)} className="text-sm text-blue-600 hover:underline">
                Can't remediate this? Request an exception →
              </button>
            )}
          </div>
        )}

        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-3">Messages</h2>
          <CommentThread comments={finding.comments} onSend={async (body) => { await api.addFindingComment(id, body); load(); }} />
        </div>
      </main>
    </div>
  );
}
