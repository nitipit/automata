import asyncio
import os

import pytest
import pytest_asyncio
from runtime import KernelRuntime


@pytest_asyncio.fixture
async def kernel():
    runtime = KernelRuntime()
    await runtime.start()
    initial_pid = runtime.km.provisioner.pid
    try:
        yield runtime
    finally:
        final_pid = runtime.km.provisioner.pid
        await runtime.close()
        for pid in {initial_pid, final_pid}:
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)


async def test_shared_identity_serialization_and_partial_error(kernel):
    identity = kernel.state["object_id"]
    first, second = await asyncio.gather(
        kernel.execute("saved_counter = counter; counter.value += 3", "python"),
        kernel.execute("counter.value += 2", "browser"),
    )
    assert first["state"]["count"] == 3
    assert second["state"]["count"] == 5
    assert second["state"]["object_id"] == identity
    result = await kernel.execute("assert saved_counter is counter; counter.value += 7; raise ValueError('after mutation')")
    assert result["status"] == "error"
    assert result["state"]["count"] == 12  # No transaction or rollback.
    assert result["reply_received"] and result["idle_received"]
    assert result["request_id"] not in {first["request_id"], second["request_id"]}
    assert {e["source"] for e in kernel.events if e["kind"] == "state"} >= {"browser", "python"}


async def test_interrupt_busy_loop_and_continue(kernel):
    command = asyncio.create_task(kernel.execute("counter.value = 9\nwhile True: pass", timeout=20))
    queue = asyncio.Queue()
    kernel.listeners.add(queue)
    try:
        while (await asyncio.wait_for(queue.get(), 5))["kind"] != "busy":
            pass
        # Busy event precedes submission; wait for kernel to begin execution.
        await asyncio.sleep(0.3)
        await kernel.interrupt()
        result = await asyncio.wait_for(command, 5)
        assert result["status"] == "error"
        assert "KeyboardInterrupt" in result["error"]
        assert result["state"]["count"] == 9
        assert (await kernel.execute("counter.value += 1"))["state"]["count"] == 10
    finally:
        kernel.listeners.discard(queue)


async def test_timeout_output_bound_and_no_interactive_stdin(kernel):
    result = await kernel.execute("print('x' * 20000)")
    assert len(result["output"]) == 8192 and result["truncated"]
    stdin = await kernel.execute("input('not permitted: ')")
    assert stdin["status"] == "error"
    assert "StdinNotImplementedError" in stdin["error"]
    timeout = await kernel.execute("counter.value = 4\nwhile True: pass", timeout=0.3)
    assert timeout["status"] == "timeout" and timeout["state"]["count"] == 4
    assert timeout["idle_received"] and timeout["reply_received"]
    assert (await kernel.execute("counter.value += 1"))["state"]["count"] == 5


async def test_restart_loses_memory_no_replay_and_no_arbitrary_repr(kernel, tmp_path):
    marker = tmp_path / "side-effect"
    await kernel.execute(f"counter.value = 88; remembered = 123; open({str(marker)!r}, 'w').write('effect')")
    generation = kernel.generation
    await kernel.restart()
    assert kernel.generation == generation + 1 and kernel.state["count"] == 0
    assert marker.read_text() == "effect"  # Restart cannot undo outside effects.
    missing = await kernel.execute("remembered")
    assert missing["status"] == "error" and "NameError" in missing["error"]
    assert any(e["kind"] == "state_lost" for e in kernel.events)
    result = await kernel.execute('''
class Dangerous:
    def __repr__(self):
        raise AssertionError("repr must not be called by inspection")
counter.value = Dangerous()
''')
    assert result["status"] == "ok" and result["state"] is None
    assert any(e["kind"] == "projection_error" for e in kernel.events)
    assert (await kernel.execute("counter.value = 6"))["state"]["count"] == 6
