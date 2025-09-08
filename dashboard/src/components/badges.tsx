import clsx from "clsx";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-crit/20 text-crit border-crit/30",
  high: "bg-bad/15 text-bad border-bad/30",
  medium: "bg-warn/15 text-warn border-warn/30",
  low: "bg-accent/10 text-accent border-accent/30",
};

const CATEGORY_COLORS: Record<string, string> = {
  security: "bg-crit/15 text-crit border-crit/30",
  bug: "bg-bad/15 text-bad border-bad/30",
  performance: "bg-warn/15 text-warn border-warn/30",
  style: "bg-muted/15 text-muted border-muted/30",
  suggestion: "bg-accent/10 text-accent border-accent/30",
};

function PillBase({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xxs font-medium uppercase tracking-wide",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: string | null | undefined }) {
  if (!severity) return <span className="text-muted">—</span>;
  const cls =
    SEVERITY_COLORS[severity] || "bg-panel2 text-muted border-border";
  return <PillBase className={cls}>{severity}</PillBase>;
}

export function CategoryBadge({ category }: { category: string | null | undefined }) {
  if (!category) return <span className="text-muted">—</span>;
  const cls =
    CATEGORY_COLORS[category] || "bg-panel2 text-muted border-border";
  return <PillBase className={cls}>{category}</PillBase>;
}

export function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "completed"
      ? "bg-ok/15 text-ok border-ok/30"
      : status === "skipped"
        ? "bg-muted/15 text-muted border-muted/30"
        : status === "failed"
          ? "bg-bad/15 text-bad border-bad/30"
          : "bg-warn/15 text-warn border-warn/30";
  return <PillBase className={cls}>{status}</PillBase>;
}
