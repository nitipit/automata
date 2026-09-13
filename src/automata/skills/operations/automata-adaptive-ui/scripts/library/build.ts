import esbuildMetadata from "esbuild/package.json" with { type: "json" };
import { fileURLToPath } from "node:url";

// Invoked by scripts/build.py only in its disposable runtime workspace.
const root = new URL("./", import.meta.url);
const esbuild = new URL("node_modules/esbuild/bin/esbuild", root);

if (esbuildMetadata.version !== "0.25.11") {
  throw new Error(`Expected esbuild 0.25.11, found ${esbuildMetadata.version}`);
}

try {
  const info = await Deno.stat(esbuild);
  if (!info.isFile) throw new Error("The cached esbuild entry is not a file");
} catch (error) {
  if (error instanceof Deno.errors.NotFound) {
    throw new Error(
      "The cached esbuild entry is unavailable; obtain confirmation before fetching dependencies",
    );
  }
  throw error;
}

const nodeVersion = await commandOutput("node", ["--version"]);
const nodeMatch = /^v(\d+)\.(\d+)\./.exec(nodeVersion);
const nodeMajor = Number(nodeMatch?.[1]);
const nodeMinor = Number(nodeMatch?.[2]);
if (
  !Number.isInteger(nodeMajor) || !Number.isInteger(nodeMinor) ||
  nodeMajor < 20 || (nodeMajor === 20 && nodeMinor < 19)
) {
  throw new Error(
    `Adaptive UI builds require Node >=20.19; found ${nodeVersion}`,
  );
}

await Deno.mkdir(new URL("dist/", root), { recursive: true });
const process = new Deno.Command("node", {
  args: [
    fileURLToPath(esbuild),
    fileURLToPath(new URL("src/ui/adaptive-ui.ts", root)),
    "--bundle",
    `--outfile=${fileURLToPath(new URL("dist/adaptive-ui.js", root))}`,
    "--format=esm",
    "--platform=browser",
    "--target=es2022",
  ],
  clearEnv: true,
  cwd: root,
  stdin: "null",
  stdout: "inherit",
  stderr: "inherit",
}).spawn();
const status = await process.status;
if (!status.success) {
  throw new Error(`esbuild failed with exit code ${status.code}`);
}

async function commandOutput(command: string, args: string[]): Promise<string> {
  let output: Deno.CommandOutput;
  try {
    output = await new Deno.Command(command, {
      args,
      clearEnv: true,
      stdin: "null",
      stdout: "piped",
      stderr: "piped",
    }).output();
  } catch (error) {
    if (error instanceof Deno.errors.NotFound) {
      throw new Error("Adaptive UI builds require Node >=20.19 on PATH");
    }
    throw error;
  }
  const decoder = new TextDecoder();
  const stdout = decoder.decode(output.stdout).trim();
  if (!output.success) {
    throw new Error(
      `Failed to run ${command}: ${
        decoder.decode(output.stderr).trim() || stdout
      }`,
    );
  }
  return stdout;
}
