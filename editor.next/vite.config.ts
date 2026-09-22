/// <reference types="vitest/config" />
import { defineConfig } from "vite";

// // https://vite.dev/config/
// import path from "node:path";
// import { fileURLToPath } from "node:url";
// const dirname =
//   typeof __dirname !== "undefined" ? __dirname : (
//     path.dirname(fileURLToPath(import.meta.url))
//   );

export default defineConfig({
  server: { host: "0.0.0.0", allowedHosts: ["cobweb.local"] },
  plugins: [],
});
