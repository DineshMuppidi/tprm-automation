import { useState } from "react";
import type { FindingComment } from "../../lib/types";

const AUTHOR_LABEL: Record<FindingComment["author_type"], string> = {
  vendor: "Vendor", internal: "Compliance Team", system: "System",
};
const AUTHOR_STYLE: Record<FindingComment["author_type"], string> = {
  vendor: "bg-blue-50 border-blue-200",
  internal: "bg-slate-100 border-slate-300",
  system: "bg-purple-50 border-purple-200",
};

interface Props {
  comments: FindingComment[];
  onSend: (body: string) => Promise<void>;
}

export default function CommentThread({ comments, onSend }: Props) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);

  async function handleSend() {
    if (!text.trim()) return;
    setSending(true);
    try {
      await onSend(text);
      setText("");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="space-y-2 max-h-72 overflow-y-auto">
        {comments.length === 0 && <p className="text-sm text-slate-400">No messages yet.</p>}
        {comments.map((c) => (
          <div key={c.id} className={`rounded-md border p-2 text-sm ${AUTHOR_STYLE[c.author_type]}`}>
            <div className="flex justify-between text-xs text-slate-500 mb-0.5">
              <span className="font-medium">{AUTHOR_LABEL[c.author_type]}</span>
              <span>{new Date(c.created_at).toLocaleString()}</span>
            </div>
            {c.body}
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          value={text} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Send a message..."
          className="flex-1 rounded-md border border-slate-300 p-2 text-sm"
        />
        <button
          onClick={handleSend} disabled={sending || !text.trim()}
          className="rounded-md bg-slate-700 text-white text-sm px-3 py-2 hover:bg-slate-800 disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}
