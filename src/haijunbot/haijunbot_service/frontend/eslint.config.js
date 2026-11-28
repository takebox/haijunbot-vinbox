// ESLint flat config (Flat Config, ESLint 10)
// Applies to frontend .js / .vue files, using the vue plugin's base rules.
// Kept lenient: only the base recommended rules, to avoid noise on existing code.
import js from "@eslint/js";
import pluginVue from "eslint-plugin-vue";
import globals from "globals";

export default [
  {
    ignores: ["dist/**", "node_modules/**"],
  },
  js.configs.recommended,
  ...pluginVue.configs["flat/recommended"],
  {
    files: ["**/*.js", "**/*.vue"],
    languageOptions: {
      // The frontend runs in a browser environment; provide globals like window/navigator/console/Blob/URL
      globals: {
        ...globals.browser,
      },
    },
    rules: {
      // Frontend code uses console for debugging extensively, so no-console stays off
      "no-console": "off",
      "no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      // Handled by the Vue template compiler; disable template-related errors to avoid false positives
      "vue/multi-word-component-names": "off",
      "vue/no-v-html": "off",
    },
  },
];
