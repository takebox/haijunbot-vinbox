import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";
import { readFileSync } from "node:fs";
import { fileURLToPath, URL } from "node:url";

// Read the frontend version from package.json and inject __APP_VERSION__ at build time for runtime display
const pkg = JSON.parse(
  readFileSync(new URL("./package.json", import.meta.url), "utf-8"),
);

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      // Use the full Vue build (with the runtime template compiler) so plugin frontend extensions can render via template strings.
      // Plugin JS uses window.Vue; with the runtime-only build compile is an empty stub and templates cannot be compiled.
      // The $ requires an exact match on 'vue' to avoid catching subpaths like 'vue/dist/...'.
      "vue$": fileURLToPath(new URL("./node_modules/vue/dist/vue.esm-bundler.js", import.meta.url)),
    },
  },
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version || ""),
  },
  server: {
    port: 5173,
    host: "127.0.0.1",
    allowedHosts: ["haijunbot-front.tocmcc.cn", "hjb-ai.cn"],
  },
  test: {
    // Vue component tests need a DOM environment
    environment: "jsdom",
    // Only include vitest cases (.test.js/.spec.js); node:test *.test.mjs
    // is handled by 'node --test', so vitest does not mistakenly scan node:test files
    include: ["src/**/*.test.js", "src/**/*.spec.js"],
  },
});
