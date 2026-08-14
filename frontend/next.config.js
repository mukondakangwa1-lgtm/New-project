// @ts-check

/** @type {import('next').NextConfig} */
const backendInternalUrl = process.env.BACKEND_INTERNAL_URL || "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
  eslint: {
    ignoreDuringBuilds: true,
  },
  // Security headers on every entry point (LAN + tunnels). TLS itself is
  // terminated by the Tailscale funnel edge, so users already get a trusted
  // HTTPS secure-context (required for the mic). HSTS pins the HTTPS session
  // once seen; the other headers are harmless hardening. NOTE: HSTS is only
  // honoured on HTTPS responses, so the plain-HTTP LAN fallbacks (:80, :3000)
  // keep working unchanged.
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendInternalUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
