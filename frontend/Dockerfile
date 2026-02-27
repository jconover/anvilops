# ---------------------------------------------------------------------------
# AnvilOps Frontend — Multi-stage production Dockerfile
# Next.js 15 / React 19 / Node 20 Alpine
#
# Standalone output is NOT enabled in next.config.mjs, so the runner stage
# requires node_modules (production-only) alongside the .next build output.
# ---------------------------------------------------------------------------

# ---- Stage 1: Install ALL dependencies (dev + prod) for the build step ----
FROM node:20-alpine AS deps
WORKDIR /app

# libc6-compat is needed for some native Node modules on Alpine
RUN apk add --no-cache libc6-compat

COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

# ---- Stage 2: Build the Next.js application ------------------------------
FROM node:20-alpine AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build-time environment variables baked into the client bundle.
# Pass via --build-arg at docker build time:
#   docker build --build-arg NEXT_PUBLIC_API_URL=https://api.example.com .
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

# Opt out of Next.js anonymous telemetry
ENV NEXT_TELEMETRY_DISABLED=1

# Ensure public/ exists even if the source tree has none yet, so COPY
# in the runner stage never fails.
RUN mkdir -p public

RUN npm run build

# Prune devDependencies so only production deps remain for the runner.
RUN npm prune --omit=dev

# ---- Stage 3: Production runner ------------------------------------------
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
# Default port — can be overridden at runtime
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

RUN apk add --no-cache libc6-compat

# Create a non-root user/group for running the application
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy the pruned production node_modules from the builder
COPY --from=builder /app/node_modules ./node_modules

# Copy the compiled Next.js output
COPY --from=builder /app/.next ./.next

# Copy public assets (directory is guaranteed to exist via mkdir in builder)
COPY --from=builder /app/public ./public

# Copy package.json (required by `npm start` / `next start`)
COPY --from=builder /app/package.json ./package.json

# Copy next.config.mjs (needed at runtime for rewrites, headers, etc.)
COPY --from=builder /app/next.config.mjs ./next.config.mjs

# Set correct ownership on the .next cache so the non-root user can write to it
RUN mkdir -p .next/cache && chown -R nextjs:nodejs .next

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["npm", "start"]
