/** @type {import('next').NextConfig} */
const nextConfig = {
  // Produce a self-contained build under .next/standalone for minimal Docker images
  output: 'standalone',

  // Proxy API requests to FastAPI backend in development
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
