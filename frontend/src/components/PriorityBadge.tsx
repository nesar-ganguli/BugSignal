type PriorityBadgeProps = {
  label: string;
};

const priorityStyles: Record<string, string> = {
  "P0 Critical": "border-red-200 bg-red-50 text-red-700",
  "P1 High": "border-orange-200 bg-orange-50 text-orange-700",
  "P2 Medium": "border-yellow-200 bg-yellow-50 text-yellow-800",
  "P3 Low": "border-emerald-200 bg-emerald-50 text-emerald-700",
};

export function PriorityBadge({ label }: PriorityBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded border px-2 py-1 text-xs font-semibold ${
        priorityStyles[label] ?? "border-slate-200 bg-slate-50 text-slate-700"
      }`}
    >
      {label}
    </span>
  );
}
