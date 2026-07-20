# syntax=docker/dockerfile:1.7

# ---------- deps ----------
FROM node:22-alpine AS deps

WORKDIR /app
# Installed from the lockfile alone, so this layer survives every source edit.
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci


# ---------- builder ----------
FROM node:22-alpine AS builder

WORKDIR /app
# Building is the memory-hungry step; a heap ceiling makes V8 collect rather than grow until the
# kernel kills it, which matters on a small host.
ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_OPTIONS=--max-old-space-size=1024

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# The dashboard is `force-dynamic`, so nothing is prerendered and the build needs no API or
# secrets — the origin and private key are read per request.
RUN npm run build


# ---------- runtime ----------
FROM node:22-alpine AS runtime

WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0 \
    NODE_OPTIONS=--max-old-space-size=256

RUN addgroup -g 10001 nodejs && adduser -u 10001 -G nodejs -S nextjs

# `output: "standalone"` emits server.js plus only the traced dependencies, so no node_modules
# tree ships here. Static assets are not traced, hence the second copy.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["node", "server.js"]
