import metadata from "echarts/package.json" with { type: "json" };
import mermaidMetadata from "mermaid/package.json" with { type: "json" };

// Use ECharts' official standalone browser ESM build; no extra bundler needed.
const packageRoot = new URL("./", import.meta.resolve("echarts/package.json"));
const output = new URL("../../../../../.agents/var/apps/dashboard/public/", import.meta.url);
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
// Mermaid's official standalone bundle includes its browser dependencies. No CDN,
// lazy remote chunks, node_modules, source maps or dependency source are served.
if (mermaidMetadata.version !== "11.12.2") throw new Error("Unexpected Mermaid version");
const mermaidRoot = new URL("./", import.meta.resolve("mermaid/package.json"));
await Deno.copyFile(new URL("dist/mermaid.min.js", mermaidRoot), new URL("mermaid.js", library));
await Deno.copyFile(new URL("LICENSE", mermaidRoot), new URL("mermaid-LICENSE.txt", library));
// Maintained Jinja templates and explicitly allowlisted modules are served from
// source co-location; never copy template sources into the public build tree.
console.log(`Built ECharts ${metadata.version} and Mermaid ${mermaidMetadata.version} under ${library.pathname}`);
