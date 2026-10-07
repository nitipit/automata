import * as esbuild from "esbuild";
const root = new URL("../", import.meta.url);
try {
  await esbuild.build({
    absWorkingDir: root.pathname,
    entryPoints: ["web/live-counter.ts"],
    outdir: "browser",
    bundle: true,
    format: "esm",
    platform: "browser",
    target: "es2022",
    nodePaths: [new URL("node_modules/", root).pathname],
    alias: {
      "@devcapsule/adapter": "@jsr/devcapsule__adapter",
      ...Object.fromEntries(["base", "button", "card"].map((name) => [
        `@adaptive/${name}`, new URL(import.meta.resolve(`@adaptive/${name}`)).pathname,
      ])),
    },
    logLevel: "info",
  });
} finally {
  esbuild.stop();
}
