import { useEffect, useRef, useState } from "react";
import type { EvidenceOut, Question, ResponseOut } from "../lib/types";
import ClassificationBadge from "./ClassificationBadge";
import EvidenceUpload from "./EvidenceUpload";

interface Props {
  question: Question;
  response: ResponseOut | undefined;
  evidence: EvidenceOut[];
  readOnly: boolean;
  onSave: (answer: string) => Promise<void>;
  onAnalyze: () => Promise<void>;
  onUploadEvidence: (file: File) => Promise<void>;
}

export default function QuestionCard({
  question, response, evidence, readOnly, onSave, onAnalyze, onUploadEvidence,
}: Props) {
  const [value, setValue] = useState(response?.raw_answer ?? "");
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">("idle");
  const [analyzing, setAnalyzing] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setValue(response?.raw_answer ?? "");
  }, [response?.raw_answer, question.id]);

  function handleChange(next: string) {
    setValue(next);
    if (readOnly) return;
    setSaveState("saving");
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      await onSave(next);
      setSaveState("saved");
    }, 700);
  }

  async function handleAnalyze() {
    setAnalyzing(true);
    try {
      await onAnalyze();
    } finally {
      setAnalyzing(false);
    }
  }

  const analysis = response?.analysis;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium text-slate-900">{question.prompt}</p>
          {question.help_text && <p className="text-sm text-slate-500 mt-0.5">{question.help_text}</p>}
        </div>
        {question.evidence_required && (
          <span className="shrink-0 text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
            Evidence required
          </span>
        )}
      </div>

      {question.input_type === "text" && (
        <textarea
          className="w-full rounded-md border border-slate-300 p-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-slate-100"
          rows={3}
          value={value}
          disabled={readOnly}
          onChange={(e) => handleChange(e.target.value)}
          placeholder="Type your answer..."
        />
      )}

      {(question.input_type === "select" || question.input_type === "boolean") && (
        <div className="flex flex-wrap gap-2">
          {(question.options?.choices ?? ["Yes", "No"]).map((choice) => (
            <button
              key={choice}
              type="button"
              disabled={readOnly}
              onClick={() => handleChange(choice)}
              className={`px-3 py-1.5 rounded-md text-sm border transition ${
                value === choice
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-white text-slate-700 border-slate-300 hover:border-blue-400"
              } disabled:opacity-60`}
            >
              {choice}
            </button>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between text-xs text-slate-400 h-4">
        <span>
          {saveState === "saving" && "Saving..."}
          {saveState === "saved" && "Saved"}
        </span>
        {!readOnly && (
          <button
            type="button"
            onClick={handleAnalyze}
            disabled={analyzing || !value.trim()}
            className="text-blue-600 hover:underline disabled:text-slate-300 disabled:no-underline"
          >
            {analyzing ? "Checking..." : "Check my answer"}
          </button>
        )}
      </div>

      {analysis?.classification && (
        <div className="rounded-md bg-slate-50 border border-slate-200 p-3 space-y-1">
          <ClassificationBadge classification={analysis.classification} />
          {analysis.follow_up_question && (
            <p className="text-sm text-slate-700">{analysis.follow_up_question}</p>
          )}
        </div>
      )}

      <EvidenceUpload evidence={evidence} readOnly={readOnly} onUpload={onUploadEvidence} />
    </div>
  );
}
