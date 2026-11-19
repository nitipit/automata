"""Create once on a specifically selected, already running IPython BrowserHost."""

import ast
import asyncio
import hashlib
import os
import secrets
from contextlib import contextmanager, suppress
from pathlib import Path

from .server_control import ServerError, admission_from, origin_port, selection, valid_id
from .status import connection_info

_CREATE_SECONDS = 55  # The retained host bounds native Pi startup to 45 seconds.
_READ_SECONDS = 3
_PAIR_SECONDS = 12
_HELPER = "__import__('automata.tools.web.engine', fromlist=['kernel_probe'])"
_REFUSALS = {
    "engine_host_missing",
    "engine_project_mismatch",
    "engine_host_not_running",
    "engine_host_incompatible",
    "engine_host_changed",
    "invalid_request",
    "host_closed",
    "capacity",
    "native_unavailable",
}


class EngineError(Exception):
    """A sanitized fixed diagnostic, not an IPython traceback or execution output."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def kernel_probe(host, project):
    """Run in the selected kernel, without starting or modifying its host."""
    from .host import BrowserHost

    if not isinstance(host, BrowserHost):
        return {"error": "engine_host_missing"}
    if host._project != Path(project):
        return {"error": "engine_project_mismatch"}
    if not host._started or host._closed or not host.runtime._running:
        return {"error": "engine_host_not_running"}
    if not getattr(host._runtime, "memory_bridge", False):
        return {"error": "engine_host_incompatible"}
    origin = host.runtime.origin
    origin_port(origin)
    # The pinned runtime owns a fresh random token per host. A domain-separated
    # fingerprint identifies this exact instance without sending its credential.
    identity = hashlib.sha256(
        f"automata-engine-host:{os.getpid()}:{id(host)}:{origin}:{host.runtime.token}".encode()
    ).hexdigest()
    return {"identity": identity, "origin": origin}


def _bound_host(host, project, identity):
    probe = kernel_probe(host, project)
    if "error" in probe:
        return probe["error"]
    if probe["identity"] != identity:
        return "engine_host_changed"
    return None


async def kernel_create(host, project, identity, options):
    """Recheck the binding immediately before the single mutating host call."""
    from .host import SessionAdmissionError

    if error := _bound_host(host, project, identity):
        return {"error": error}
    try:
        admitted = await host.admit_session(**selection(options))
    except (ServerError, SessionAdmissionError) as exc:
        if exc.code in _REFUSALS:
            return {"error": exc.code}
        raise
    return {"session_id": admitted.session_id, "url": admitted.url}


def kernel_paired(host, project, identity, session_id):
    """Observe the same instance's pair, without blocking the kernel shell."""
    from .status import client_connected

    if error := _bound_host(host, project, identity):
        return {"error": error}
    entry = host._entries.get(session_id)
    return {
        "connected": bool(
            entry and not entry.retiring and not entry.chat._dead and client_connected(entry)
        )
    }


@contextmanager
def _client(path):
    try:
        info = connection_info(path)
    except (OSError, ValueError, RecursionError):
        raise EngineError("invalid_connection_file") from None
    try:
        from jupyter_client import AsyncKernelClient
    except ImportError:
        raise EngineError("jupyter_client_unavailable") from None
    try:
        client = AsyncKernelClient()
        client.load_connection_info(info)
        client.start_channels(stdin=False, hb=False, control=False, iopub=False)
    except Exception:
        if "client" in locals():
            with suppress(Exception):
                client.stop_channels()
        raise EngineError("engine_unavailable") from None
    try:
        yield client
    finally:
        with suppress(Exception):
            client.stop_channels()


async def _execute(client, expression, *, code="", timeout=_READ_SECONDS):
    async with asyncio.timeout(timeout):
        reply = await client.execute(
            code,
            silent=True,
            store_history=False,
            allow_stdin=False,
            user_expressions={"automata": expression},
            reply=True,  # AsyncKernelClient correlates the shell reply by parent msg_id.
            timeout=timeout,
        )
    content = reply["content"]
    if content["status"] != "ok":
        raise ValueError
    response = content["user_expressions"]["automata"]
    text = response["data"]["text/plain"] if response["status"] == "ok" else None
    if not isinstance(text, str) or len(text) > 4096:
        raise ValueError
    data = ast.literal_eval(text)
    if not isinstance(data, dict):
        raise ValueError
    return data


def _refused(data):
    error = data.get("error")
    if set(data) == {"error"} and isinstance(error, str) and error in _REFUSALS:
        raise EngineError(error)


async def _probe(client, project):
    try:
        probe = await _execute(
            client, f"{_HELPER}.kernel_probe(globals().get('host'), {project!r})"
        )
        _refused(probe)
        identity, origin = probe["identity"], probe["origin"]
        if (
            not isinstance(identity, str)
            or len(identity) != 64
            or any(c not in "0123456789abcdef" for c in identity)
        ):
            raise ValueError
        origin_port(origin)
        return identity, origin
    except EngineError:
        raise
    except TimeoutError:
        raise EngineError("engine_probe_timeout") from None
    except Exception:
        raise EngineError("engine_probe_failed") from None


async def _create(client, project, identity, options):
    # Await on IPython's own asyncio loop (which also owns BrowserHost). Retrieve
    # and remove the ephemeral binding only in the correlated silent shell reply.
    slot = f"_automata_engine_{secrets.token_hex(12)}"
    code = (
        f"{slot} = await {_HELPER}.kernel_create(globals().get('host'), "
        f"{project!r}, {identity!r}, {options!r})"
    )
    try:
        data = await _execute(
            client, f"globals().pop({slot!r})", code=code, timeout=_CREATE_SECONDS
        )
    except TimeoutError:
        raise EngineError("engine_create_timeout") from None
    except Exception:
        raise EngineError("engine_create_unconfirmed") from None
    _refused(data)
    return data


async def create_chat(path, project, target, options):
    """Return only the public outcome, retaining a known ID on later failure."""
    from .bidi import BiDiError, connect_firefox
    from .browser import BrowserError

    result = {"session_id": None, "browser_connected": False, "creation": "not_created"}
    try:
        options = selection(options)
        with _client(path) as client:
            project = str(project)
            identity, origin = await _probe(client, project)
            browser = await asyncio.to_thread(connect_firefox, target)
            try:
                result["creation"] = "unknown"
                try:
                    data = await _create(client, project, identity, options)
                except EngineError as exc:
                    if exc.code in _REFUSALS:
                        result["creation"] = "not_created"
                    raise
                sid = data.get("session_id")
                if not valid_id(sid):
                    raise EngineError("engine_create_unconfirmed")
                result.update(session_id=sid, creation="created")
                try:
                    admission = admission_from(data)
                except ServerError:
                    raise EngineError("engine_admission_invalid") from None
                if not admission.url.startswith(origin + "/"):
                    raise EngineError("engine_admission_invalid")
                await asyncio.to_thread(browser.open_chat, admission, origin)
                paired = (
                    f"{_HELPER}.kernel_paired(globals().get('host'), "
                    f"{project!r}, {identity!r}, {sid!r})"
                )
                try:
                    async with asyncio.timeout(_PAIR_SECONDS):
                        while True:
                            if await asyncio.to_thread(browser.chat_ready):
                                state = await _execute(client, paired)
                                _refused(state)
                                if state == {"connected": True} and await asyncio.to_thread(
                                    browser.chat_ready
                                ):
                                    result["browser_connected"] = True
                                    break
                            await asyncio.sleep(0.1)
                except (EngineError, BrowserError):
                    raise
                except Exception:
                    raise EngineError("browser_connection_unconfirmed") from None
            finally:
                await asyncio.to_thread(browser.close)
    except (EngineError, ServerError, BiDiError) as exc:
        result["error"] = exc.code
    except BrowserError:
        result["error"] = "browser_open_failed" if result["session_id"] else "browser_unavailable"
    return result
