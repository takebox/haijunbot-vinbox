import { createApp } from "vue";
import * as Vue from "vue";
// Explicitly import the runtime template compiler from the full Vue build (in the
// runtime-only build, compile is an empty stub, so plugin frontends using template
// strings cannot compile and will render empty). Hence the named import exposed on
// window.Vue keeps the compiler from being tree-shaken by the bundler.
import { compile } from "vue/dist/vue.esm-bundler.js";
import App from "./App.vue";
import "./style.css";

// Expose global Vue for plugin frontend extensions (ES modules dynamically loaded at runtime).
// Plugin JS does not import 'vue' (to avoid npm module resolution) and instead uses render
// functions through window.Vue. Actually call compile once so the bundler keeps the runtime
// template compiler (otherwise tree-shaking strips parse/transform that compile depends on).
compile("<div></div>");
window.Vue = Object.assign({}, Vue, { compile });

createApp(App).mount("#app");

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((error) => {
      console.error("[PWA] Service worker registration failed:", error);
    });
  });
}
