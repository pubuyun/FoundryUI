export default defineNuxtConfig({
  devtools: { enabled: true },
  future: {
    compatibilityVersion: 4,
  },
  typescript: {
    typeCheck: true,
  },
  vite: {
    ssr: {
      noExternal: [
        "baklavajs",
        "@baklavajs/core",
        "@baklavajs/engine",
        "@baklavajs/events",
        "@baklavajs/interface-types",
        "@baklavajs/renderer-vue",
      ],
    },
  },
});
