import type { NextConfig } from 'next';
const backend = (process.env.BACKEND_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '');
const nextConfig: NextConfig = {
  devIndicators: false,
  async rewrites() {
    // Vercel Services routes /api directly to Python on the same public origin.
    // Keep the local/external proxy for development and standalone frontend hosting.
    if (process.env.VERCEL && !process.env.BACKEND_URL) return [];
    return [{source: '/api/:path*', destination: `${backend}/api/:path*`}];
  },
};
export default nextConfig;
