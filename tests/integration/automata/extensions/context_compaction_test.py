"""Test the compaction wrapper with isolated Pi/TypeBox adapters, without model calls."""

import json
import os
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest


def test_context_compaction_runtime_boundaries(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js 22.18+ is required for TypeScript runtime tests")

    extension = tmp_path / "context-compaction.ts"
    extension.write_text(
        files("automata")
        .joinpath("runtimes", "pi", "extensions", "context-compaction.ts")
        .read_text()
    )
    package = tmp_path / "node_modules" / "typebox"
    package.mkdir(parents=True)
    (package / "package.json").write_text(
        json.dumps({"type": "module", "exports": "./index.js"})
    )
    (package / "index.js").write_text(
        "export const Type = {"
        "String: options => ({type: 'string', ...options}),"
        "Optional: schema => schema,"
        "Object: (properties, options) => ({type: 'object', properties, ...options})"
        "};"
    )

    pi_package = tmp_path / "node_modules" / "@earendil-works" / "pi-coding-agent"
    pi_package.mkdir(parents=True)
    (pi_package / "package.json").write_text(
        json.dumps({"type": "module", "exports": "./index.js"})
    )
    (pi_package / "index.js").write_text(
        "export const CONFIG_DIR_NAME = '.pi';"
        "export function getAgentDir() { return '/tmp/automata-test-agent-dir'; }"
        "export function convertToLlm(messages) { return messages; }"
        "export function serializeConversation(messages) { return JSON.stringify(messages); }"
        "export async function compact(preparation, model, apiKey, headers, "
        "customInstructions, signal, thinkingLevel, streamFn, env) {"
        "  if (globalThis.__nativeCompactionFailure) throw globalThis.__nativeCompactionFailure;"
        "  globalThis.__nativeCompactions ??= [];"
        "  globalThis.__nativeCompactions.push({preparation, model, apiKey, headers, "
        "customInstructions, signal, thinkingLevel, streamFn, env});"
        "  if (globalThis.__nativeCompactionGate) await globalThis.__nativeCompactionGate;"
        "  if (streamFn) {"
        "    const call = globalThis.__nativeCompactions.at(-1);"
        "    const sharedContext = globalThis.__reuseNativeContext"
        "      ? {systemPrompt: 'shared-system',"
        " messages: [{role: 'user', content: [{type: 'text', text: 'shared'}]}]}"
        "      : undefined;"
        "    const invoke = async (systemPrompt, text) => {"
        "      const context = sharedContext ?? globalThis.__nativeContextOverride ??"
        " {systemPrompt, messages: [{role: 'user', content: [{type: 'text', text}]}]};"
        "      if (globalThis.__freezeNativeContext) globalThis.__freezeNativeContext(context);"
        "      const stream = await streamFn(model, context, {apiKey, headers, env});"
        "      const result = await stream.result();"
        "      call.streamCalls ??= []; call.streamCalls.push({context, result});"
        "      globalThis.__nativeStreamResult = result;"
        "    };"
        "    if (preparation.isSplitTurn && preparation.turnPrefixMessages.length > 0) {"
        "      if (preparation.messagesToSummarize.length > 0)"
        " await invoke('history-system', 'history prompt');"
        "      await invoke('prefix-system', 'prefix prompt');"
        "    } else {"
        "      await invoke('history-system', 'history prompt');"
        "    }"
        "  }"
        "  return {summary: 'native summary', firstKeptEntryId: preparation.firstKeptEntryId, "
        "tokensBefore: preparation.tokensBefore, usage: {input: 1, output: 1, cacheRead: 0, "
        "cacheWrite: 0, totalTokens: 2, cost: {input: 0, output: 0, cacheRead: 0, "
        "cacheWrite: 0, total: 0}}};"
        "}"
    )

    result = subprocess.run(
        [node, "--test", str(Path(__file__).with_suffix(".mjs"))],
        env={**os.environ, "CONTEXT_TEST_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
