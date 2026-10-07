import asyncio

import pytest
from runtime import KernelRuntime


async def test_bounded_queue_rejects_without_submitting_code():
    kernel = KernelRuntime()
    await kernel.start()
    try:
        # Hold the same lock an active execution owns; no second request may pass.
        await kernel.lock.acquire()
        try:
            with pytest.raises(RuntimeError, match="code not submitted"):
                await kernel.execute("counter.value = 999")
        finally:
            kernel.lock.release()
        assert kernel.state["count"] == 0 and kernel.healthy
        assert (await kernel.execute("assert counter.value == 0"))["status"] == "ok"
    finally:
        await kernel.close()
