"""Read-only observations. A transport pair is not proof of Firefox control."""

import ast
import asyncio
import json
import os
import stat
from pathlib import Path

from .server_control import ServerError, valid_id


def client_connected(entry):
    from starlette.websockets import WebSocketState

    pair = entry.pair
    browser = entry.chat.connector.session
    return bool(
        pair
        and pair.ready
        and not pair.cleanup
        and browser
        and browser.is_connected
        and pair.chat_socket.client_state is WebSocketState.CONNECTED
        and pair.chat_socket.application_state is WebSocketState.CONNECTED
    )


def host_snapshot(host):
    if host._closed or not host._started:
        return {"state": "not_running"}
    return {
        "state": "running",
        "sessions": [
            {"id": sid, "client_connected": client_connected(entry)}
            for sid, entry in sorted(host._entries.items())
            if not entry.retiring and not entry.chat._dead
        ],
    }


def kernel_snapshot(host, project):
    """Executed in the selected kernel, including kernels predating the CLI."""
    from .host import BrowserHost

    if not isinstance(host, BrowserHost):
        return {"state": "unknown", "reason": "no_retained_host"}
    if host._project != Path(project):
        return {"state": "unknown", "reason": "different_project"}
    return host_snapshot(host)


def validate(data):
    if isinstance(data, dict):
        if data == {"state": "not_running"}:
            return data
        if (
            set(data) == {"state", "sessions"}
            and data["state"] == "running"
            and isinstance(data["sessions"], list)
        ):
            if all(
                isinstance(s, dict)
                and set(s) == {"id", "client_connected"}
                and valid_id(s["id"])
                and type(s["client_connected"]) is bool
                for s in data["sessions"]
            ):
                return data
    raise ServerError("incompatible")


def managed_status(project):
    from .server import endpoint_for

    try:
        return validate(endpoint_for(project).inspect())
    except ServerError as exc:
        if exc.code == "not_running":
            return {"state": "not_running"}
        return {"state": "unknown", "reason": exc.code}
    except OSError:
        return {"state": "unknown", "reason": "runtime_unavailable"}


def connection_info(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or st.st_mode & 0o077:
            raise ValueError
        raw = stream.read(8193)
    if len(raw) > 8192:
        raise ValueError
    info = json.loads(raw)
    if (
        not isinstance(info, dict)
        or info.get("transport") != "tcp"
        or info.get("ip") != "127.0.0.1"
    ):
        raise ValueError
    ports = ["shell_port", "control_port", "iopub_port", "stdin_port", "hb_port"]
    if not all(type(info.get(p)) is int and 0 < info[p] < 65536 for p in ports):
        raise ValueError
    if (
        not isinstance(info.get("key"), str)
        or not info["key"]
        or info.get("signature_scheme") != "hmac-sha256"
    ):
        raise ValueError
    return {k: info[k] for k in ["ip", "transport", "key", "signature_scheme", *ports]}


async def engine_status(path, project, *, timeout=2):
    try:
        info = connection_info(path)
    except (ValueError, OSError):
        return {"state": "unknown", "reason": "invalid_connection_file"}
    try:
        from jupyter_client import AsyncKernelClient
    except ImportError:
        return {"state": "unknown", "reason": "jupyter_client_unavailable"}
    client = AsyncKernelClient()
    try:
        client.load_connection_info(info)
        client.start_channels(stdin=False, hb=False, control=False, iopub=False)
        expr = (
            "__import__('automata.tools.web.status', fromlist=['kernel_snapshot'])"
            f".kernel_snapshot(globals().get('host'), {str(project)!r})"
        )
        async with asyncio.timeout(timeout):
            # One shell reply; no output subscription, history, stdin, retries or interrupt.
            reply = await client.execute(
                "",
                silent=True,
                store_history=False,
                allow_stdin=False,
                user_expressions={"status": expr},
                reply=True,
                timeout=timeout,
            )
        result = reply["content"]["user_expressions"]["status"]
        if result["status"] == "ok":
            data = ast.literal_eval(result["data"]["text/plain"])
            if data not in (
                {"state": "unknown", "reason": "different_project"},
                {"state": "unknown", "reason": "no_retained_host"},
            ):
                data = validate(data)
            return {"state": "running", "host": data}
        return {"state": "running", "host": {"state": "unknown", "reason": "snapshot_unavailable"}}
    except TimeoutError:
        return {"state": "unknown", "reason": "timeout"}
    except Exception:
        return {"state": "unknown", "reason": "inspection_failed"}
    finally:
        client.stop_channels()
