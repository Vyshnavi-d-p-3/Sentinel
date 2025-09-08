// Typed fetch wrapper. Every call funnels through ``apiFetch`` so we can add
// auth headers, tracing, or retry policy in one place later.

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly body: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const JSON_HEADERS = { "Content-Type": "application/json" } as const;

// API key — when ``NEXT_PUBLIC_API_KEY`` is configured, every request carries
// it as ``X-API-Key``. Matches the backend's ``require_api_key`` dependency.
// Note: Next.js inlines NEXT_PUBLIC_* at build time. For per-deployment secrets
// without rebuilds, swap this for a runtime config endpoint or session cookie.
const API_KEY: string | undefined =
  typeof process !== "undefined" ? process.env.NEXT_PUBLIC_API_KEY : undefined;

const DEFAULT_FETCH_TIMEOUT_MS = 25_000;

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    ...JSON_HEADERS,
    ...((init.headers as Record<string, string>) || {}),
  };
  if (API_KEY && !headers["X-API-Key"]) {
    headers["X-API-Key"] = API_KEY;
  }

  // Abort hung requests so the UI does not spin forever when the API is down.
  let signal = init.signal;
  if (!signal && typeof AbortSignal !== "undefined" && "timeout" in AbortSignal) {
    signal = AbortSignal.timeout(DEFAULT_FETCH_TIMEOUT_MS);
  }

  // Relative paths hit the Next.js rewrite (see next.config.mjs) and get
  // proxied to the backend. Absolute URLs bypass the proxy.
  const resp = await fetch(path, {
    ...init,
    signal,
    headers,
    // The dashboard is read-only; never cache by default, each hook opts in.
    cache: init.cache ?? "no-store",
  });

  if (!resp.ok) {
    let body: unknown = null;
    try {
      body = await resp.json();
    } catch {
      /* non-JSON body; leave as null */
    }
    const detail =
      (body && typeof body === "object" && "detail" in (body as object)
        ? String((body as { detail: unknown }).detail)
        : null) || resp.statusText;
    throw new ApiError(
      `${resp.status} ${detail}`,
      resp.status,
      body,
    );
  }

  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

/** Build a querystring where undefined/null/empty values are dropped. */
export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const out = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    out.set(key, String(value));
  }
  const str = out.toString();
  return str ? `?${str}` : "";
}
