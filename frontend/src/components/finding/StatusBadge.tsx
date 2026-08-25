import type { FindingSeverity, FindingStatus } from "../../lib/types";

const SEVERITY_STYLE: Record<FindingSeverity, string> = {
  critical: "bg-red-100 text-red-800",
  high: "bg-orange-100 text-orange-800",
  medium: "bg-amber-100 text-amber-800",
  low: "bg-slate-100 text-slate-600",
};

const STATUS_STYLE: Record<FindingStatus, string> = {
  new: "bg-slate-100 text-slate-600",
  assigned: "bg-blue-100 text-blue-700",
  in_progress: "bg-blue-100 text-blue-700",
  submitted: "bg-purple-100 text-purple-700",
  validating: "bg-purple-100 text-purple-700",
  closed: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
  overdue: "bg-red-200 text-red-900",
  exception_granted: "bg-slate-200 text-slate-700",
};

const STATUS_LABEL: Record<FindingStatus, string> = {
  new: "New", assigned: "Assigned", in_progress: "In Progress", submitted: "Submitted",
  validating: "Validating", closed: "Closed", rejected: "Needs Revision", overdue: "Overdue",
  exception_granted: "Exception Granted",
};

export function SeverityBadge({ severity }: { severity: FindingSeverity }) {
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${SEVERITY_STYLE[severity]}`}>{severity}</span>;
}

export function FindingStatusBadge({ status }: { status: FindingStatus }) {
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_STYLE[status]}`}>{STATUS_LABEL[status]}</span>;
}
