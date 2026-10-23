import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:18100", ws: true } },
  },
  build: {
    outDir: "../cairn/src/cairn/workbench/static",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          graph: ["cytoscape"],
          markdown: ["react-markdown", "remark-gfm"],
          react: ["react", "react-dom"],
        },
      },
    },
  },
});
