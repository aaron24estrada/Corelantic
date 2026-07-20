import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  // Emit a server bundle carrying only the packages it actually imports, so the runtime image
  // ships no node_modules tree of its own. See apps/web/Dockerfile.
  output: "standalone",
};

export default nextConfig;
