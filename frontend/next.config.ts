import type { NextConfig } from "next";

const backendUrl = (process.env.BACKEND_INTERNAL_URL || "http://backend:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  output: "standalone",
  deploymentId: process.env.DEPLOYMENT_VERSION,
  devIndicators: {},
  turbopack: {
    root: process.cwd(),
  },
  async rewrites() {
    return {
      beforeFiles: [
        {
          source: "/api/:path*",
          destination: `${backendUrl}/api/:path*`,
        },
        {
          source: "/webhook/:path*",
          destination: `${backendUrl}/webhook/:path*`,
        },
        {
          source: "/static/:path*",
          destination: `${backendUrl}/static/:path*`,
        },
        {
          source: "/health/:path*",
          destination: `${backendUrl}/health/:path*`,
        },
      ],
      afterFiles: [],
      fallback: [],
    };
  },
};

export default nextConfig;
