import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Simplified devIndicators to pass Next.js 16 strict type checking
  devIndicators: {
    // position: "bottom-right", // Optional: Only standard properties are allowed
  },
};

export default nextConfig;