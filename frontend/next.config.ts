// ==================================================
// FILE: frontend/next.config.ts
// ==================================================

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone',
  devIndicators: {},
  async rewrites() {
    return [
      {
        // Proxy all API requests to the local FastAPI backend during development
        // This mirrors the Caddy reverse proxy behavior in production
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8000/api/:path*',
      },
    ];
  },
};

export default nextConfig;