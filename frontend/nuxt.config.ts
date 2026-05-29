import tailwindcss from "@tailwindcss/vite";

export default defineNuxtConfig({
  css: ["~/assets/css/tailwind.css"],
  devtools: { enabled: true },
  future: {
    compatibilityVersion: 4,
  },
  typescript: {
    typeCheck: true,
  },
  vite: {
    plugins: [tailwindcss()],
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
