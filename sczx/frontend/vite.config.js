import {readFileSync} from "node:fs";
import {createHash} from "node:crypto";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  plugins: [vue(), tailwindcss(),{name:"sczx-offline-shell",generateBundle(_,bundle){
    const files=Object.keys(bundle).filter(k=>/\.(js|css|woff2?|html)$/.test(k)).map(k=>"/"+k);if(!files.includes("/index.html"))files.push("/index.html");
    const name="sczx-shell-"+createHash("sha256").update(files.join("|")).digest("hex").slice(0,16);
    const source=readFileSync(new URL("./src/services/offline/service-worker.js",import.meta.url),"utf8").replace("__SCZX_CACHE__",JSON.stringify(name)).replace("__SCZX_SHELL__",JSON.stringify(files));this.emitFile({type:"asset",fileName:"sw.js",source});
  }}],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "./src") } },
  server: { proxy: { "/api": { target: process.env.SCZX_API_PROXY || "http://127.0.0.1:8000", changeOrigin: true } } },
});
