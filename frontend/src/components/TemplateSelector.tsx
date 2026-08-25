import type { TemplateOut } from "../lib/types";

interface Props {
  templates: TemplateOut[];
  value: string;
  onChange: (templateId: string) => void;
}

export default function TemplateSelector({ templates, value, onChange }: Props) {
  return (
    <select
      className="w-full rounded-md border border-slate-300 p-2 text-sm"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">Select a questionnaire template...</option>
      {templates.map((t) => (
        <option key={t.id} value={t.id}>
          {t.name} ({t.question_count} questions)
        </option>
      ))}
    </select>
  );
}
