import assert from "node:assert/strict";
import test from "node:test";
import { starterHarness } from "./starter-harness.mjs";

test("dialog Cancel, Restore and target edit fence delayed trusted client imports", async () => {
  for (const action of ["cancel-connection", "restore", "target-edit"]) {
    const {get,controls:c,context,tick} = await starterHarness();
    try {
      get("connection-settings").click(); await tick();
      c.holdImport = true;
      const pending = context.playspaceChat.connect({participant:"page",token:"synthetic"},"explicit-agent");
      await tick();
      assert.ok(c.resolveImport);
      assert.equal(get("selected-target").textContent,"explicit-agent");
      if (action === "target-edit") {
        get("target-participant").value="another-agent"; get("target-participant").fire("input");
      } else get(action).click();
      c.resolveImport();
      assert.equal(await pending,false);
      assert.equal(c.connections.length,0);
      assert.equal(get("connection").textContent,"Disconnected");
    } finally { context.playspaceChat.dispose(); }
  }
});

test("Restore supersedes an opening handshake without invalidating its own recovery intent", async () => {
  const {get,controls:c,context,tick} = await starterHarness();
  try {
    c.holdConnect=true; get("connect-session").click(); await tick();
    c.candidate={version:2,mode:"live",chat:{}};
    assert.equal(await context.playspaceChat.restore(),true);
    assert.equal(c.restorations,1);
    c.resolveConnect(); await tick(); await tick();
    assert.equal(c.clients.at(-1).closed,true);
    assert.equal(get("connection").textContent,"Disconnected");
  } finally { context.playspaceChat.dispose(); }
});
