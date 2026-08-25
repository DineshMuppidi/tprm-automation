import { useRef, useState } from "react";
import type { EvidenceOut } from "../lib/types";

interface Props {
  evidence: EvidenceOut[];
  readOnly: boolean;
  onUpload: (file: File) => Promise<void>;
}

export default function EvidenceUpload({ evidence, readOnly, onUpload }: Props) {
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFiles(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await onUpload(file);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div>
      {evidence.length > 0 && (
        <ul className="mb-2 space-y-1">
          {evidence.map((e) => (
            <li key={e.id} className="text-xs text-slate-600 flex items-center gap-1.5">
              <span aria-hidden>📎</span> {e.original_filename}
              <span className="text-slate-400">({e.document_type})</span>
            </li>
          ))}
        </ul>
      )}
      {!readOnly && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files); }}
          onClick={() => inputRef.current?.click()}
          className={`cursor-pointer rounded-md border border-dashed p-2 text-center text-xs transition ${
            dragOver ? "border-blue-500 bg-blue-50 text-blue-600" : "border-slate-300 text-slate-400 hover:border-slate-400"
          }`}
        >
          {uploading ? "Uploading..." : "Drag & drop a file here, or click to attach evidence"}
          <input
            ref={inputRef}
            type="file"
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />
        </div>
      )}
    </div>
  );
}
