# ---------------------------------------------------------------------------
# AnvilOps Frontend — Multi-stage production Dockerfile
# Next.js 15 / React 19 / Node 20 Alpine
#
# Uses Next.js standalone output mode for minimal production images.
# The standalone build bundles only the required node_modules, eliminating
# the need to copy the full dependency tree into the runner stage.
# ---------------------------------------------------------------------------

# ---- Stage 1: Install ALL dependencies (dev + prod) for the build step ----
FROM node:20.19-alpine3.21 AS deps
WORKDIR /app

# libc6-compat is needed for some native Node modules on Alpine
RUN apk add --no-cache libc6-compat

COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

# ---- Stage 2: Build the Next.js application ------------------------------
FROM node:20.19-alpine3.21 AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build-time environment variables baked into the client bundle.
# Pass via --build-arg at docker build time:
#   docker build --build-arg NEXT_PUBLIC_API_URL=https://api.example.com .
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

# Server-side backend URL for Next.js API proxy rewrites.
# Must be an absolute URL (e.g. http://anvilops-api:80).
# Defaults to http://localhost:8000 for local development.
ARG BACKEND_URL=http://localhost:8000
ENV BACKEND_URL=${BACKEND_URL}

# Opt out of Next.js anonymous telemetry
ENV NEXT_TELEMETRY_DISABLED=1

# Ensure public/ exists even if the source tree has none yet, so COPY
# in the runner stage never fails.
RUN mkdir -p public

RUN npm run build

# ---- Stage 3: Production runner ------------------------------------------
FROM node:20.19-alpine3.21 AS runner
WORKDIR /app

ARG BUILD_DATE
ARG GIT_SHA
ARG VERSION=dev

LABEL org.opencontainers.image.title="AnvilOps Frontend" \
      org.opencontainers.image.description="Server provisioning platform web UI" \
      org.opencontainers.image.source="https://github.com/jconover/anvilops" \
      org.opencontainers.image.vendor="AnvilOps" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${GIT_SHA}"

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
# Default port — can be overridden at runtime
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Create a non-root user/group for running the application
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy the standalone server (includes bundled minimal node_modules)
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./

# Copy static assets (not included in standalone output)
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Copy public assets (directory is guaranteed to exist via mkdir in builder)
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["node", "server.js"]
