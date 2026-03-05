/** @type {import('next').NextConfig} */
const nextConfig = {
  // Produce a self-contained build under .next/standalone for minimal Docker images
  output: 'standalone',

  // Proxy API requests to FastAPI backend.
  // In production with ALB Ingress, /api/* is routed directly to the backend
  // so this rewrite only fires when accessing the Next.js server directly
  // (e.g. local development or kubectl port-forward).
  // BACKEND_URL must be an absolute URL — relative paths break the proxy.
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.BACKEND_URL || 'http://localhost:8000'}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
