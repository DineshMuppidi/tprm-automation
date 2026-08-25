import type { Classification } from "../lib/types";

const STYLES: Record<Classification, string> = {
  strong: "bg-green-100 text-green-800",
  adequate: "bg-amber-100 text-amber-800",
  weak: "bg-orange-100 text-orange-800",
  missing: "bg-red-100 text-red-800",
  contradictory: "bg-red-200 text-red-900",
};

export default function ClassificationBadge({ classification }: { classification: Classification | null }) {
  if (!classification) {
    return <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-500">Not analyzed</span>;
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STYLES[classification]}`}>
      {classification.charAt(0).toUpperCase() + classification.slice(1)}
    </span>
  );
}
