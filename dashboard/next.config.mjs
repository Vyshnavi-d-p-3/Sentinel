/** @type {import('next').NextConfig} */
// Standalone bundle is only emitted when STANDALONE_BUILD=1 (Dockerfile sets it).
// Omitting it locally avoids flaky dev watchers / `.next` issues on macOS (EMFILE).
const standalone =
  process.env.STANDALONE_BUILD === "1" || process.env.DOCKER_BUILD === "1";

const nextConfig = {
  reactStrictMode: true,
  ...(standalone ? { output: "standalone" } : {}),
  poweredByHeader: false,
  // Proxy /api/* to the FastAPI backend so the dashboard can ship as a
  // single origin without worrying about CORS. Override with NEXT_PUBLIC_API_URL
  // when talking to a remote backend.
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      { source: "/api/:path*", destination: `${apiUrl}/api/:path*` },
      { source: "/health", destination: `${apiUrl}/health` },
    ];
  },
  // Hardening: deny clickjacking, MIME-type sniffing, etc. These complement
  // the FastAPI backend's security headers — both layers ship them so an
  // operator can serve the dashboard from a separate CDN if they want.
  async headers() {
    const securityHeaders = [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Permissions-Policy", value: "geolocation=(), microphone=(), camera=()" },
    ];
    return [{ source: "/(.*)", headers: securityHeaders }];
  },
};

export default nextConfig;
