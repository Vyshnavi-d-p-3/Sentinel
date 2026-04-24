import { ApiError } from "@/lib/api";

export type FormattedErrorTone = "danger" | "warning" | "info";

export type FormattedError = {
  title: string;
  lines: string[];
  status?: number;
  tone: FormattedErrorTone;
  /** Hint for sensitive states (401/403) */
  hint?: string;
};

function httpTitle(status: number): string {
  switch (status) {
    case 400:
      return "Invalid request";
    case 401:
      return "Unauthorized";
    case 403:
      return "Forbidden";
    case 404:
      return "Not found";
    case 413:
      return "Request too large";
    case 429:
      return "Too many requests";
    default:
      if (status >= 500) return "Server error";
      return `Request failed`;
  }
}

function toneForStatus(status: number): FormattedErrorTone {
  if (status === 429) return "warning";
  if (status === 401 || status === 403) return "danger";
  if (status >= 500) return "danger";
  if (status === 404) return "info";
  return "danger";
}

function hintForStatus(status: number): string | undefined {
  if (status === 401 || status === 403) {
    return "If the API is key-protected, set NEXT_PUBLIC_API_KEY to match the backend API_KEY.";
  }
  if (status === 429) {
    return "Wait a moment and retry, or adjust rate limits if you operate the service.";
  }
  return undefined;
}

function detailLinesFromBody(body: unknown): string[] {
  if (body == null || typeof body !== "object") return [];
  if (!("detail" in body)) return [];

  const d = (body as { detail: unknown }).detail;
  if (typeof d === "string") return [d];
  if (Array.isArray(d)) {
    return d.map((item) => {
      if (item && typeof item === "object" && "msg" in item) {
        const msg = String((item as { msg: unknown }).msg);
        const loc = (item as { loc?: unknown }).loc;
        if (Array.isArray(loc) && loc.length > 0) {
          const path = loc.map((x) => String(x)).join(".");
          return `${path}: ${msg}`;
        }
        return msg;
      }
      return String(item);
    });
  }
  return [];
}

/** Normalize any thrown value from React Query / fetch into a structured error. */
export function formatApiError(error: unknown): FormattedError {
  if (error instanceof ApiError) {
    const lines = detailLinesFromBody(error.body);
    const fallback = error.message.replace(/^\d{3}\s+/, "").trim();
    return {
      title: httpTitle(error.status),
      lines: lines.length > 0 ? lines : fallback ? [fallback] : ["Unknown error detail"],
      status: error.status,
      tone: toneForStatus(error.status),
      hint: hintForStatus(error.status),
    };
  }

  if (error instanceof Error) {
    const msg = error.message;
    const looksNetwork =
      /failed to fetch|networkerror|load failed|fetch failed|econnrefused|network request failed|aborted|timeout/i.test(
        msg,
      );
    return {
      title: looksNetwork ? "Cannot reach the API" : "Error",
      lines: [msg],
      tone: "danger",
      hint: looksNetwork
        ? "The Next.js app proxies /health and /api/* to the backend (see next.config.mjs → NEXT_PUBLIC_API_URL, default http://127.0.0.1:8000). Start the API: cd backend && uvicorn app.main:app --reload, or run docker compose up from the repo root. If the UI is on HTTPS, the API must be HTTPS too (or use same-origin / a reverse proxy) to avoid mixed-content blocks."
        : undefined,
    };
  }

  return {
    title: "Error",
    lines: ["Something went wrong."],
    tone: "danger",
  };
}
