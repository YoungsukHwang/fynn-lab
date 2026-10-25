import type { NextConfig } from "next";

// FYNN_STATIC_SITE=1 builds the static site for GitHub Pages: plain files in out/, served under
// FYNN_BASE_PATH (for example /fynn-lab). There is no server, so no redirects, and the Demo page shows
// recorded replies (results/demo/recorded.json) instead of calling the backend.
const staticSite = process.env.FYNN_STATIC_SITE === "1";

const nextConfig: NextConfig = {
  ...(staticSite
    ? { output: "export", trailingSlash: true, basePath: process.env.FYNN_BASE_PATH || undefined }
    : {
        // Old eval URLs: the pages moved into sections with Framework and Results tabs, and Noise & A/A
        // became Online evaluation.
        async redirects() {
          return [
            { source: "/framework", destination: "/before-after/framework", permanent: false },
            { source: "/results", destination: "/before-after/results", permanent: false },
            { source: "/before-after", destination: "/before-after/results", permanent: false },
            { source: "/skill-edits", destination: "/skill-edits/results", permanent: false },
            { source: "/noise", destination: "/online-evaluation", permanent: false },
            { source: "/noise/:path*", destination: "/online-evaluation", permanent: false },
          ];
        },
      }),
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
