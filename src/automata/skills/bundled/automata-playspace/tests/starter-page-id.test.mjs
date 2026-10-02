import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs/promises";
import path from "node:path";
import { starterHarness } from "./starter-harness.mjs";

test("readonly Page ID uses authenticated server participant, not Agent target; unpaired shows placeholder", async () => {
  const html = await fs.readFile(path.join(path.dirname(process.env.PLAYSPACE_LIB),"index.html"),"utf8");
  assert.match(html,/<dt>Page ID<\/dt>\s*<dd id="page-participant" role="status">Not approved yet<\/dd>/);
  assert.doesNotMatch(html,/<input[^>]*id="page-participant"/);
  const {get,controls:c,context,tick} = await starterHarness();
  try {
    assert.equal(get("page-participant").textContent,"page");
    c.participant="authenticated-browser-42";
    get("connection-settings").click(); await tick();
    assert.equal(get("page-participant").textContent,"authenticated-browser-42");
    assert.notEqual(get("page-participant").textContent,get("target-participant").value);
    get("target-participant").value="another-agent"; get("target-participant").fire("input"); await tick();
    assert.equal(get("page-participant").textContent,"authenticated-browser-42");
    get("close-connection").click();
    c.authenticated=false; // unauthenticated status may still carry an irrelevant participant
    get("connection-settings").click(); await tick();
    assert.equal(get("page-participant").textContent,"Not approved yet");
    assert.equal(c.connections.length,0);
  } finally { context.playspaceChat.dispose(); }
});
