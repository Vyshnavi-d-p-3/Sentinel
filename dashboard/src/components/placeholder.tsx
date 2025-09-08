import Link from "next/link";

export function PagePlaceholder({
  title,
  description,
  endpoint,
}: {
  title: string;
  description: string;
  endpoint?: string;
}) {
  return (
    <div className="space-y-4">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">{title}</h1>
        <p className="text-sm text-muted">{description}</p>
      </header>
      <div className="rounded-lg border border-dashed border-border bg-panel/40 px-6 py-16 text-center">
        <p className="text-sm text-muted">
          Page UI coming in a later slice.
          {endpoint && (
            <>
              {" "}
              Data source:{" "}
              <code className="rounded bg-panel2 px-1.5 py-0.5 text-xs text-accent">
                {endpoint}
              </code>
              .
            </>
          )}
        </p>
        <Link
          href="/"
          className="mt-4 inline-block text-sm text-accent hover:underline"
        >
          ← Back to home
        </Link>
      </div>
    </div>
  );
}
