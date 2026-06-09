import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Disable the development indicator button on the bottom left
  devIndicators: {
    appIsrStatus: false,
    buildActivity: false,
  },
};

export default nextConfig;