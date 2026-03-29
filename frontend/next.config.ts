// import type { NextConfig } from "next";
// const withBundleAnalyzer = require("@next/bundle-analyzer")({
//   enabled: process.env.ANALYZE === "true",
// });

// const nextConfig: NextConfig = {
//   output: "standalone",
//   // ── Performance ────────────────────────────────────────────────────────────
//   compress: true,
//   poweredByHeader: false,
//   reactStrictMode: true,

//   // ── Images ─────────────────────────────────────────────────────────────────
//   images: {
//     formats: ["image/avif", "image/webp"],
//     remotePatterns: [
//       { protocol: "https", hostname: "tissatech.com" },
//       { protocol: "https", hostname: "assets.tissatech.com" },
//     ],
//   },

//   // ── Security Headers ────────────────────────────────────────────────────────
//   async headers() {
//     return [
//       {
//         source: "/(.*)",
//         headers: [
//           { key: "X-DNS-Prefetch-Control", value: "on" },
//           { key: "X-XSS-Protection", value: "1; mode=block" },
//           { key: "X-Frame-Options", value: "DENY" },
//           { key: "X-Content-Type-Options", value: "nosniff" },
//           { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
//           { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
//           {
//             key: "Content-Security-Policy",
//             value: [
//               "default-src 'self'",
//               "script-src 'self' 'unsafe-eval' 'unsafe-inline'",
//               "style-src 'self' 'unsafe-inline'",
//               "img-src 'self' data: https:",
//               `connect-src 'self' ${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}`,
//               "font-src 'self'",
//               "frame-ancestors 'none'",
//             ].join("; "),
//           },
//         ],
//       },
//     ];
//   },

//   // ── Env vars exposed to browser (non-secret only) ─────────────────────────
//   env: {
//     NEXT_PUBLIC_APP_NAME: "TissaTech AI",
//     NEXT_PUBLIC_APP_VERSION: "1.0.0",
//   },
// };

// export default withBundleAnalyzer(nextConfig);

import type { NextConfig } from "next";

const withBundleAnalyzer = require("@next/bundle-analyzer")({
  enabled: process.env.ANALYZE === "true",
});

const nextConfig: NextConfig = {
  output: "standalone",

  // ── Performance ────────────────────────────────────────────────────────────
  compress: true,
  poweredByHeader: false,
  reactStrictMode: true,

  // ── Images ─────────────────────────────────────────────────────────────────
  images: {
    formats: ["image/avif", "image/webp"],
    remotePatterns: [
      { protocol: "https", hostname: "tissatech.com" },
      { protocol: "https", hostname: "assets.tissatech.com" },

      // 👇 Added from chatbot config
      { protocol: "https", hostname: "cdn-icons-png.flaticon.com" },
      { protocol: "https", hostname: "images.unsplash.com" },
    ],
  },

  // ── Security Headers ────────────────────────────────────────────────────────
  async headers() {
    return [
      // ✅ MAIN APP (secure)
      {
        source: "/(.*)",
        headers: [
          { key: "X-DNS-Prefetch-Control", value: "on" },
          { key: "X-XSS-Protection", value: "1; mode=block" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-eval' 'unsafe-inline'",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: https:",
              `connect-src 'self' ${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}`,
              "font-src 'self'",
              // Allow embedding (widget runs in an iframe created by embed.js on customer sites)
              "frame-ancestors *",
            ].join("; "),
          },
        ],
      },

      // ✅ CHATBOT WIDGET (allow iframe embedding)
      {
        source: "/widget/:path*",
        headers: [
          {
            key: "Content-Security-Policy",
            value: [
              "default-src *",
              "script-src * 'unsafe-inline' 'unsafe-eval'",
              "style-src * 'unsafe-inline'",
              "img-src * data:",
              "connect-src *",
              "frame-ancestors *",
            ].join("; "),
          },
        ],
      },
    ];
  },

  // ── Env vars exposed to browser ────────────────────────────────────────────
  env: {
    NEXT_PUBLIC_APP_NAME: "TissaTech AI",
    NEXT_PUBLIC_APP_VERSION: "1.0.0",
  },
};

export default withBundleAnalyzer(nextConfig);