"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/reviews", label: "Reviews" },
  { href: "/try-review", label: "Try a review" },
  { href: "/eval", label: "Eval" },
  { href: "/costs", label: "Costs" },
  { href: "/prompts", label: "Prompts" },
  { href: "/feedback", label: "Feedback" },
  { href: "/settings", label: "Settings" },
] as const;

export function Nav() {
  const pathname = usePathname();
  return (
    <nav className="flex items-center gap-1 border-b border-border bg-panel px-4 py-3">
      <Link
        href="/"
        className="mr-4 flex items-center gap-2 rounded text-sm font-semibold tracking-tight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/55 focus-visible:ring-offset-2 focus-visible:ring-offset-panel"
      >
        <span
          aria-hidden
          className="inline-block h-2 w-2 rounded-full bg-accent shadow-[0_0_10px_theme(colors.accent)]"
        />
        Sentinel
      </Link>
      {NAV.map((item) => {
        const active =
          item.href === "/"
            ? pathname === "/"
            : pathname?.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={clsx(
              "rounded px-3 py-1.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/55 focus-visible:ring-offset-2 focus-visible:ring-offset-panel",
              active
                ? "bg-panel2 text-fg"
                : "text-muted hover:text-fg hover:bg-panel2",
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
