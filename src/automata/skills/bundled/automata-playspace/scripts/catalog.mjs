// Private build-time DOM shim only; examples execute real bundled Edictor validators.
import { writeFile, access } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { load, installDOM } from "../tests/runtime.mjs";
installDOM();
const { generateCatalog } = await load("catalog.js");
const catalog = generateCatalog();
const destination = resolve(process.argv[2]);
const publicRoot = dirname(destination);
for (const source of [catalog.envelopes.source, ...catalog.entries.flatMap(entry => entry.sources)]) {
  if (!source.startsWith("./lib/") || !source.endsWith(".js") || source.includes(".."))
    throw new Error("Invalid public module reference");
  await access(resolve(publicRoot, source));
}
await writeFile(destination, JSON.stringify(catalog, null, 2) + "\n");
