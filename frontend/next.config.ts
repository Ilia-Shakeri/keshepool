import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  compress: true,
  deploymentId: process.env.DEPLOYMENT_VERSION,
  devIndicators: {},
  turbopack: {
    root: process.cwd(),
  },
};

export default nextConfig;
