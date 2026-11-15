import { build } from "esbuild";
import { mkdir, copyFile } from "node:fs/promises";
import { resolve } from "node:path";

// Only this flat output is public. Never publish sources or dependency trees.
const root = new URL("../", import.meta.url);
const output = process.argv[2] ? resolve(process.argv[2]) : new URL("src/automata/tools/web/public/", root).pathname;
await mkdir(output, { recursive: true });
await build({
  entryPoints: [new URL("src/automata/tools/web/frontend/index.ts", root).pathname],
  outfile: resolve(output, "index.js"),
  bundle: true,
  format: "esm",
  platform: "browser",
  target: "es2022",
  minify: true,
  sourcemap: false,
  external: ["/bridge.js"],
  legalComments: "inline",
});
// Distribution keeps the dependency license alongside the bundle, not its sources.
await copyFile(new URL("node_modules/@devcapsule/adapter/LICENSE.md", root), resolve(output, "adapter-LICENSE.txt"));
console.log("Built browser assets (Adapter 4.0.0) without exposing source or credentials.");
