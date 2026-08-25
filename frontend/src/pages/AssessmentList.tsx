import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../components/Header";
import ProgressBar from "../components/ProgressBar";
import { api } from "../lib/api";
import type { AssessmentSummary } from "../lib/types";

const STATUS_LABEL: Record<string, string> = {
  draft: "Not started", assigned: "Not started", in_progress: "In progress",
  submitted: "Submitted", under_review: "Under review", completed: "Completed", expired: "Expired",
};

export default function AssessmentList() {
  const [assessments, setAssessments] = useState<AssessmentSummary[] | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.myAssessments().then(setAssessments);
  }, []);

  return (
    <div className="min-h-screen bg-slate-50">
      <Header />
      <main className="max-w-4xl mx-auto px-4 py-8">
        <h1 className="text-lg font-semibold text-slate-900 mb-1">Your Assessments</h1>
        <p className="text-sm text-slate-500 mb-6">
          Complete each assigned security assessment before its due date. Progress is saved automatically.
        </p>

        {assessments === null && <p className="text-slate-400 text-sm">Loading...</p>}
        {assessments?.length === 0 && (
          <p className="text-slate-400 text-sm">No assessments have been assigned to you yet.</p>
        )}

        <div className="space-y-3">
          {assessments?.map((a) => (
            <button
              key={a.id}
              onClick={() => navigate(a.status === "completed" ? `/assessments/${a.id}/result` : `/assessments/${a.id}`)}
              className="w-full text-left bg-white rounded-lg border border-slate-200 p-4 hover:border-blue-400 transition"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-medium text-slate-900">{a.template_name}</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {STATUS_LABEL[a.status] ?? a.status}
                    {a.due_at && a.status !== "completed" && ` · Due ${new Date(a.due_at).toLocaleDateString()}`}
                  </p>
                </div>
                {a.overall_score !== null && (
                  <span className="text-sm font-semibold text-slate-700">{a.overall_score.toFixed(0)}/100</span>
                )}
              </div>
              {a.status !== "completed" && (
                <div className="mt-3">
                  <ProgressBar pct={a.progress_pct} />
                </div>
              )}
            </button>
          ))}
        </div>
      </main>
    </div>
  );
}
