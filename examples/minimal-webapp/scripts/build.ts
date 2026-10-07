import * as esbuild from "esbuild";

const root = new URL("../", import.meta.url);
const options: esbuild.BuildOptions = {
  absWorkingDir: root.pathname,
  entryPoints: ["app/templates/base.ts"],
  outdir: "browser",
  bundle: true,
  format: "esm",
  platform: "browser",
  target: "es2022",
  // No source maps: source templates/internal modules are not served publicly.
  nodePaths: [new URL("node_modules/", root).pathname],
  alias: {
    "@devcapsule/adapter": "@jsr/devcapsule__adapter",
    ...Object.fromEntries(
      ["base", "button", "card", "tokens"].map((name) => [
        `@adaptive/${name}`,
        new URL(import.meta.resolve(`@adaptive/${name}`)).pathname,
      ]),
    ),
  },
  logLevel: "info",
};

if (Deno.args.includes("--watch")) {
  const context = await esbuild.context(options);
  await context.watch();
  console.log(
    "Watching templates' TypeScript; refresh the browser after edits.",
  );
  const stop = async () => {
    await context.dispose();
    esbuild.stop();
    Deno.exit();
  };
  Deno.addSignalListener("SIGINT", stop);
  Deno.addSignalListener("SIGTERM", stop);
  await new Promise(() => {});
} else {
  try {
    await esbuild.build(options);
  } finally {
    esbuild.stop();
  }
}
