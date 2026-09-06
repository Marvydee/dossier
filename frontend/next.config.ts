import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Without this, the dev server's HMR websocket silently fails (and blocks
  // hydration entirely — forms fall back to native submission) when accessed
  // via 127.0.0.1 instead of localhost, even though both point at the same
  // server. Verified live: identical request, only the Origin header differs
  // (http://127.0.0.1:3000 vs http://localhost:3000), and only the former
  // gets a malformed response from Turbopack's dev server. This explicitly
  // trusts both hostnames so it works regardless of which one is typed.
  allowedDevOrigins: ["localhost", "127.0.0.1"],
};

export default nextConfig;
