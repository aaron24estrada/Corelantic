import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// Only the pure modules are tested here — the chart-spec adapter and the formatters. They are
// where the hand-written logic lives, and neither needs a DOM. The canvas in `<Chart>` has no
// behaviour of its own worth mocking a renderer for.
export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
});
