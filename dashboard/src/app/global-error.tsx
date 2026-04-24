"use client";

/**
 * Root error boundary. Must define its own html/body (Next App Router).
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full bg-[#0b0d10] p-8 text-[#e6e9ef]">
        <h1 className="text-xl font-semibold">Sentinel</h1>
        <p className="mt-2 text-sm opacity-80">{error.message || "A critical error occurred."}</p>
        <button
          type="button"
          className="mt-4 rounded border border-white/20 px-3 py-1.5 text-sm"
          onClick={() => reset()}
        >
          Try again
        </button>
      </body>
    </html>
  );
}
