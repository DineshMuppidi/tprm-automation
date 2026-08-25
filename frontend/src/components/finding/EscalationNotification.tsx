import type { FindingDetail } from "../../lib/types";

export default function EscalationNotification({ finding }: { finding: FindingDetail }) {
  if (finding.status === "overdue") {
    return (
      <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-800">
        <strong>Overdue.</strong> This finding passed its due date ({new Date(finding.due_at).toLocaleDateString()}).
        Category management and compliance have been notified.
      </div>
    );
  }
  if (finding.status === "rejected") {
    const lastComment = [...finding.comments].reverse().find((c) => c.author_type === "system" || c.author_type === "internal");
    return (
      <div className="rounded-md bg-amber-50 border border-amber-200 p-3 text-sm text-amber-800">
        <strong>Needs revision.</strong>{" "}
        {lastComment ? lastComment.body : "Your last submission needs more work — see comments below."}
      </div>
    );
  }
  if (finding.rejection_count >= 2) {
    return (
      <div className="rounded-md bg-orange-50 border border-orange-200 p-3 text-sm text-orange-800">
        This finding has been sent back for revision {finding.rejection_count} times — it has been flagged for
        additional review.
      </div>
    );
  }
  return null;
}
