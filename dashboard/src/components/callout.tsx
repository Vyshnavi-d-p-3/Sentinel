import clsx from "clsx";
import type { ReactNode } from "react";

export type CalloutVariant =
  | "info"
  | "success"
  | "warning"
  | "danger"
  /** Security / privacy guidance (blue + soft yellow wash) */
  | "security";

const variantClass: Record<CalloutVariant, string> = {
  info: "border-l-info bg-info/[0.08] text-fg ring-1 ring-inset ring-info/20",
  success:
    "border-l-ok bg-ok/[0.08] text-fg ring-1 ring-inset ring-ok/20",
  warning:
    "border-l-warn bg-warn/[0.10] text-fg ring-1 ring-inset ring-warn/25",
  danger:
    "border-l-bad bg-bad/[0.09] text-fg ring-1 ring-inset ring-bad/25",
  security:
    "border-l-info bg-[linear-gradient(105deg,rgba(56,189,248,0.08)_0%,rgba(250,204,21,0.06)_100%)] text-fg ring-1 ring-inset ring-info/25",
};

const accentText: Record<CalloutVariant, string> = {
  info: "text-info",
  success: "text-ok",
  warning: "text-warn",
  danger: "text-bad",
  security: "text-info",
};

function Icon({ variant }: { variant: CalloutVariant }) {
  const common = "h-5 w-5 shrink-0";
  switch (variant) {
    case "success":
      return (
        <svg className={clsx(common, "text-ok")} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      );
    case "warning":
      return (
        <svg className={clsx(common, "text-warn")} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      );
    case "danger":
      return (
        <svg className={clsx(common, "text-bad")} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      );
    case "security":
      return (
        <svg className={clsx(common, "text-info")} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
        </svg>
      );
    case "info":
    default:
      return (
        <svg className={clsx(common, "text-info")} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      );
  }
}

export function Callout({
  variant,
  title,
  children,
  className,
  icon,
  role,
}: {
  variant: CalloutVariant;
  title?: string;
  children: ReactNode;
  className?: string;
  /** Override default icon */
  icon?: ReactNode;
  role?: "status" | "alert";
}) {
  const r =
    role ?? (variant === "danger" ? "alert" : "status");
  return (
    <div
      role={r}
      className={clsx(
        "rounded-r-lg border-l-4 py-3 pl-3 pr-4 text-sm leading-relaxed shadow-sm",
        variantClass[variant],
        className,
      )}
    >
      <div className="flex gap-3">
        <span className="mt-0.5">{icon ?? <Icon variant={variant} />}</span>
        <div className="min-w-0 flex-1 space-y-1">
          {title && (
            <div className={clsx("font-semibold tracking-tight", accentText[variant])}>
              {title}
            </div>
          )}
          <div className="text-fg/95 [&_code]:rounded [&_code]:bg-panel2 [&_code]:px-1 [&_code]:py-0.5 [&_code]:text-xs">
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
