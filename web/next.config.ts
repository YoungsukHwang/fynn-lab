import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The eval pages moved into three sections, each with Framework and Results tabs.
  async redirects() {
    return [
      { source: "/framework", destination: "/before-after/framework", permanent: false },
      { source: "/results", destination: "/before-after/results", permanent: false },
      { source: "/before-after", destination: "/before-after/results", permanent: false },
      { source: "/skill-edits", destination: "/skill-edits/results", permanent: false },
      { source: "/noise", destination: "/noise/results", permanent: false },
    ];
  },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
