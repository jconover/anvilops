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

  async headers() {
    const securityHeaders = [
      {
        key: 'Content-Security-Policy',
        value: [
          "default-src 'self'",
          "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
          "style-src 'self' 'unsafe-inline'",
          "img-src 'self' data: blob:",
          "font-src 'self' data:",
          "connect-src 'self' https://cognito-idp.*.amazonaws.com",
          "frame-ancestors 'none'",
          "base-uri 'self'",
          "form-action 'self'",
        ].join('; '),
      },
      {
        key: 'X-Frame-Options',
        value: 'DENY',
      },
      {
        key: 'X-Content-Type-Options',
        value: 'nosniff',
      },
      {
        key: 'Referrer-Policy',
        value: 'strict-origin-when-cross-origin',
      },
      {
        key: 'Permissions-Policy',
        value: 'camera=(), microphone=(), geolocation=()',
      },
    ];

    // Only add HSTS in production to avoid breaking local dev on localhost
    if (process.env.NODE_ENV === 'production') {
      securityHeaders.push({
        key: 'Strict-Transport-Security',
        value: 'max-age=63072000; includeSubDomains; preload',
      });
    }

    return [
      {
        // Apply security headers to all non-API routes
        source: '/((?!api/).*)',
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
