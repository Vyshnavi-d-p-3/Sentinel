"use client";

import { useEffect } from "react";

/**
 * Catches client-side render errors. Without this, Next dev can show
 * "missing required error components, refreshing…" in a bad loop.
 */
export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // eslint-disable-next-line no-console -- operator visibility in dev
    console.error("dashboard app error:", error);
  }, [error]);

  return (
    <div className="mx-auto max-w-lg px-4 py-16 text-center">
      <h1 className="text-xl font-semibold text-fg">Something went wrong</h1>
      <p className="mt-2 text-sm text-muted">
        {error.message || "An unexpected error occurred in the browser."}
      </p>
      {error.digest ? (
        <p className="mt-2 font-mono text-xs text-muted">Digest: {error.digest}</p>
      ) : null}
      <button
        type="button"
        className="mt-6 rounded-md border border-border bg-panel2 px-4 py-2 text-sm text-fg hover:border-accent/50"
        onClick={() => reset()}
      >
        Try again
      </button>
      <p className="mt-8 text-xs text-muted">
        If you recently ran <code className="rounded bg-panel2 px-1">next dev --turbo</code>, run{" "}
        <code className="rounded bg-panel2 px-1">rm -rf .next &amp;&amp; npm run build</code> before{" "}
        <code className="rounded bg-panel2 px-1">npm start</code>.
      </p>
    </div>
  );
}
