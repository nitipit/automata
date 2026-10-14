import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import metadata from "echarts/package.json" with { type: "json" };

// Copy the official pinned standalone ESM build; never publish dependency trees.
// An explicit output permits isolated task evidence without touching installed data.
const packageRoot = new URL("./", import.meta.resolve("echarts/package.json"));
const output = Deno.args[0]
  ? pathToFileURL(resolve(Deno.args[0]) + "/")
  : new URL("../../../../../.agents/var/tools/automata-anatomy/public/", import.meta.url);
const library = new URL("lib/", output);
if (metadata.version !== "6.0.0") throw new Error("Unexpected ECharts version");

await Deno.mkdir(library, { recursive: true });
for (const [source, destination] of [
  ["dist/echarts.esm.min.js", "echarts.js"],
  ["LICENSE", "echarts-LICENSE.txt"],
  ["NOTICE", "echarts-NOTICE.txt"],
]) {
  await Deno.copyFile(new URL(source, packageRoot), new URL(destination, library));
}
// Adaptive UI/Mermaid/Prism are reviewed viewer assets already in the tool package.
console.log(`Prepared ECharts ${metadata.version} under ${library.pathname}`);
