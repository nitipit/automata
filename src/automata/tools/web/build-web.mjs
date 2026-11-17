import { build } from "esbuild";
import { mkdir, copyFile, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

// Flat reviewed outputs only; never publish sources or a dependency tree.
const root = new URL("../../../../", import.meta.url);
const output = process.argv[2] ? resolve(process.argv[2]) : new URL("src/automata/tools/web/public/", root).pathname;
await mkdir(output, { recursive: true });
for (const name of await readdir(output)) {
  if (/^(?:index|ui|connection-bootstrap|chunk-[A-Z0-9]{8})\.js$/.test(name)) await rm(resolve(output, name));
}
const result = await build({
  entryPoints: {
    "connection-bootstrap": new URL("src/automata/tools/web/frontend/connection-bootstrap.ts", root).pathname,
    index: new URL("src/automata/tools/web/frontend/index.ts", root).pathname,
    ui: new URL("src/automata/tools/web/frontend/ui.ts", root).pathname,
  },
  outdir: output,
  entryNames: "[name]",
  chunkNames: "chunk-[hash]",
  bundle: true,
  splitting: true,
  format: "esm",
  platform: "browser",
  target: "es2022",
  minify: true,
  sourcemap: false,
  external: ["/bridge.js"],
  legalComments: "inline",
  loader: { ".svg": "text" },
  metafile: true,
});
await copyFile(new URL("node_modules/@devcapsule/adapter/LICENSE.md", root), resolve(output, "adapter-LICENSE.txt"));
const licenses = [
  ["@devcapsule/adapter", "LICENSE.md"], ["@arrow-js/core", "LICENSE.txt"],
  ["culori", "LICENSE"], ["highlight.js", "LICENSE"], ["markdown-it", "LICENSE"],
  ["argparse", "LICENSE"], ["entities", "LICENSE"], ["linkify-it", "LICENSE"],
  ["mdurl", "LICENSE"], ["punycode.js", "LICENSE-MIT.txt"], ["uc.micro", "LICENSE.txt"],
];
const notices = [];
for (const [name, license] of licenses) {
  const directory = new URL(`node_modules/${name}/`, root);
  const metadata = JSON.parse(await readFile(new URL("package.json", directory), "utf8"));
  notices.push(`===== ${name} ${metadata.version} =====\n${await readFile(new URL(license, directory), "utf8")}`);
}
const iconNotices = new URL("src/automata/tools/web/frontend/_assets/gnomicon/", root);
for (const name of ["ATTRIBUTION.txt", "COPYING", "COPYING_CCBYSA3", "LICENSE.md"]) {
  notices.push(`===== Gnomicon edit icon: ${name} =====\n${await readFile(new URL(name, iconNotices), "utf8")}`);
}
await writeFile(resolve(output, "third-party-LICENSES.txt"), notices.join("\n\n"));
// Optional development evidence stays at an explicitly chosen path, never in shipped assets.
if (process.env.AUTOMATA_WEB_METAFILE) await writeFile(resolve(process.env.AUTOMATA_WEB_METAFILE), JSON.stringify(result.metafile));
console.log("Built local shared ESM browser graph and pinned dependency license notices.");
