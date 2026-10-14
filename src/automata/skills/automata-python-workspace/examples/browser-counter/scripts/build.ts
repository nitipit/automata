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
    plugins: [{
      name: "installed-adaptive-ui",
      setup(build) {
        build.onResolve({ filter: /^@adaptive-ui$/ }, () => ({
          path: "./lib/adaptive-ui.js", external: true,
        }));
      },
    }],
    logLevel: "info",
  });
} finally {
  esbuild.stop();
}
