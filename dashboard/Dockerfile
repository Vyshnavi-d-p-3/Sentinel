# syntax=docker/dockerfile:1.7

# ---------- Stage 1: deps -----------------------------------------------------
# Install node_modules in isolation so build-time deps don't leak into runtime.
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
# ``npm ci`` is reproducible from package-lock.json. Falls back to ``npm install``
# in repos that haven't committed a lockfile yet.
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# ---------- Stage 2: build ----------------------------------------------------
FROM node:20-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1 \
    STANDALONE_BUILD=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ---------- Stage 3: runtime --------------------------------------------------
# Slim runtime: only the standalone server output + static assets, running as
# a non-root user with a TCP healthcheck.
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN apk add --no-cache curl tini \
 && addgroup --system --gid 1001 nextjs \
 && adduser  --system --uid 1001 nextjs

# ``output: 'standalone'`` in next.config.mjs produces these directories.
COPY --from=builder --chown=nextjs:nextjs /app/public ./public
COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl --fail --silent http://127.0.0.1:${PORT}/ >/dev/null || exit 1

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["node", "server.js"]
