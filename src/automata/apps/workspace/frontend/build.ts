// Explicit output keeps development builds away from the live preview assets.
const runtime = Deno.env.get("WORKSPACE_RUNTIME_ROOT");
const root = new URL("../../../../../", import.meta.url);
const output = runtime
  ? new URL(`file://${runtime.replace(/\/$/, "")}/web-assets/`)
  : new URL(".agents/var/apps/workspace/web-assets/", root);
async function copyTree(source: URL, target: URL) {
  await Deno.mkdir(target, { recursive: true });
  for await (const entry of Deno.readDir(source)) {
    const from = new URL(entry.name + (entry.isDirectory ? "/" : ""), source);
    const to = new URL(entry.name + (entry.isDirectory ? "/" : ""), target);
    if (entry.isDirectory) await copyTree(from, to);
    else if (entry.isFile) await Deno.copyFile(from, to);
  }
}
await copyTree(new URL("../web/", import.meta.url), output);
await copyTree(new URL(".agents/tools/message-router/browser/", root), new URL("router/", output));
console.log(`Built workspace web assets at ${output.pathname}`);
