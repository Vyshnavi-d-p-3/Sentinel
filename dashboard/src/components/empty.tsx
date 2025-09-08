import clsx from "clsx";
import { Callout, type CalloutVariant } from "@/components/callout";
import { formatApiError } from "@/lib/formatError";

export function EmptyState({
  title,
  description,
  action,
  className,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={clsx(
        "flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-panel/40 px-6 py-16 text-center",
        className,
      )}
    >
      <h3 className="text-base font-medium text-fg">{title}</h3>
      {description && (
        <p className="mt-1 max-w-md text-sm text-muted">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function LoadingBar() {
  return (
    <div
      className="flex items-center gap-3 text-sm text-muted"
      role="status"
      aria-live="polite"
    >
      <span className="relative flex h-2 w-2">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent/40 opacity-60" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
      </span>
      <span>Loading…</span>
    </div>
  );
}

const calloutVariant: Record<
  ReturnType<typeof formatApiError>["tone"],
  CalloutVariant
> = {
  danger: "danger",
  warning: "warning",
  info: "info",
};

/**
 * Standard API / network error surface. Prefer passing raw `error` from React Query
 * so status codes and FastAPI `detail` arrays render cleanly.
 */
export function ErrorPanel({
  error,
  message,
}: {
  /** Raw error from useQuery / mutation (recommended) */
  error?: unknown;
  /** Plain string fallback */
  message?: string;
}) {
  const formatted =
    error !== undefined
      ? formatApiError(error)
      : formatApiError(new Error(message ?? "Unknown error"));

  const variant = calloutVariant[formatted.tone];

  return (
    <Callout variant={variant} title={formatted.title}>
      <ul className="list-inside list-disc space-y-1 text-sm">
        {formatted.lines.map((line, i) => (
          <li key={i} className="marker:text-muted">
            {line}
          </li>
        ))}
      </ul>
      {formatted.status != null && (
        <p className="mt-2 font-mono text-xxs text-muted">
          HTTP {formatted.status}
        </p>
      )}
      {formatted.hint && (
        <p className="mt-2 border-t border-border/60 pt-2 text-xs text-muted">
          {formatted.hint}
        </p>
      )}
    </Callout>
  );
}
