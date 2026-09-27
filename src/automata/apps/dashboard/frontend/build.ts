import metadata from "echarts/package.json" with { type: "json" };

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
for (const name of ["index.html", "app.js", "chart.js", "layout.css", "themes.css", "theme.js"]) {
  await Deno.copyFile(new URL(`../web/${name}`, import.meta.url), new URL(name, output));
}
console.log(`Built dashboard UI and Apache ECharts ${metadata.version} under ${output.pathname}`);
