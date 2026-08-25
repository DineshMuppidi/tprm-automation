import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Header from "../components/Header";
import ProgressBar from "../components/ProgressBar";
import QuestionCard from "../components/QuestionCard";
import { api, ApiError } from "../lib/api";
import type { AssessmentDetail } from "../lib/types";

export default function Questionnaire() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<AssessmentDetail | null>(null);
  const [submitError, setSubmitError] = useState<string[] | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(() => {
    api.getAssessment(id).then(setDetail);
  }, [id]);

  useEffect(() => { load(); }, [load]);

  if (!detail) {
    return (
      <div className="min-h-screen bg-slate-50">
        <Header />
        <p className="text-center text-slate-400 mt-12 text-sm">Loading...</p>
      </div>
    );
  }

  const readOnly = detail.status === "completed";
  const sections = Array.from(new Set(detail.questions.map((q) => q.section)));

  async function handleSubmit() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      await api.submitAssessment(id);
      navigate(`/assessments/${id}/result`);
    } catch (err) {
      if (err instanceof ApiError && err.detail && typeof err.detail === "object" && "missing" in (err.detail as object)) {
        setSubmitError((err.detail as { missing: string[] }).missing);
      } else {
        setSubmitError(["Something went wrong submitting the assessment."]);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <Header />
      <main className="max-w-3xl mx-auto px-4 py-8 space-y-6">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">{detail.template_name}</h1>
          <p className="text-sm text-slate-500">{detail.vendor_name}</p>
        </div>

        <ProgressBar pct={detail.progress_pct} />

        {sections.map((section) => (
          <div key={section} className="space-y-3">
            <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">{section}</h2>
            {detail.questions.filter((q) => q.section === section).map((q) => (
              <QuestionCard
                key={q.id}
                question={q}
                response={detail.responses[q.id]}
                evidence={detail.evidence.filter((e) => e.response_id === detail.responses[q.id]?.id)}
                readOnly={readOnly}
                onSave={async (answer) => {
                  await api.saveResponse(id, q.id, answer);
                  load();
                }}
                onAnalyze={async () => {
                  await api.analyzeResponse(id, q.id);
                  load();
                }}
                onUploadEvidence={async (file) => {
                  await api.uploadEvidence(id, q.id, file);
                  load();
                }}
              />
            ))}
          </div>
        ))}

        {!readOnly && (
          <div className="pt-4 border-t border-slate-200">
            {submitError && (
              <div className="mb-3 text-sm text-red-600">
                {submitError.length === 1 && submitError[0].startsWith("Something")
                  ? submitError[0]
                  : `Please answer all questions before submitting (${submitError.length} remaining).`}
              </div>
            )}
            <button
              onClick={handleSubmit}
              disabled={submitting || detail.progress_pct < 100}
              className="rounded-md bg-blue-600 text-white text-sm font-medium px-4 py-2 hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? "Submitting..." : "Submit assessment"}
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
