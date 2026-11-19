"""The only embedding seam for the pinned, single-browser Web Runtime."""

from __future__ import annotations

import json
from importlib.metadata import distribution

_VERSION = "0.1.0"
_COMMIT = "cba648e627082bfa39696bfdd5af6f79c2f0b281"
_INCOMPATIBLE = "Incompatible Automata Web Runtime for shared-listener Web Chat"
_FRAGMENT_BOOTSTRAP = b'var token = new URLSearchParams(location.hash.slice(1)).get("token");'
_MEMORY_BOOTSTRAP = (
    b"var token = window.__automataBridgeTicket; delete window.__automataBridgeTicket;"
)


def _memory_bridge_source(source):
    # This exact pinned artifact is a classic script, not an importable class.
    # Adapt only Web Chat's bootstrap input; its bridge and standalone runtime
    # stay unchanged. Firefox persists even a transient fragment replaceState.
    if source.count(_FRAGMENT_BOOTSTRAP) != 1:
        raise RuntimeError(_INCOMPATIBLE)
    return source.replace(_FRAGMENT_BOOTSTRAP, _MEMORY_BOOTSTRAP)


def _install_memory_bridge(runtime, assets):
    from starlette.responses import Response

    source = _memory_bridge_source((assets / "bridge.js").read_bytes())
    routes = runtime.app.router.routes
    matching = [route for route in routes if getattr(route, "path", None) == "/bridge.js"]
    if len(matching) != 1:
        raise RuntimeError(_INCOMPATIBLE)

    async def bridge(request):
        if not runtime._local_request(request):
            return Response(status_code=403)
        return Response(source, media_type="text/javascript", headers={"Cache-Control": "no-store"})

    routes.remove(matching[0])
    runtime.app.add_route("/bridge.js", bridge, methods=["GET"])


def _check_routes(runtime):
    from starlette.routing import WebSocketRoute

    routes = [route for route in runtime.app.routes if getattr(route, "path", None) == "/ws"]
    if len(routes) != 1 or not isinstance(routes[0], WebSocketRoute):
        raise RuntimeError(_INCOMPATIBLE)
    return routes[0]


def _check_child(runtime):
    if (
        getattr(runtime, "_origin", None) != ""
        or getattr(runtime, "_running", None) is not False
        or not isinstance(getattr(runtime, "token", None), str)
        or not all(callable(getattr(runtime, name, None)) for name in ("wait_for_browser", "close"))
    ):
        raise RuntimeError(_INCOMPATIBLE)
    _check_routes(runtime)


class SharedRuntime:
    def __init__(self, *, port: int):
        try:
            from automata_web_runtime import WebRuntime
            from automata_web_runtime.runtime import _browser_assets

            installed = distribution("automata-web-runtime")
            provenance = json.loads(installed.read_text("direct_url.json") or "{}")
            vcs = provenance.get("vcs_info")
            if installed.version != _VERSION or (
                vcs is not None and vcs.get("commit_id") != _COMMIT
            ):
                raise RuntimeError(_INCOMPATIBLE)
            self.parent = WebRuntime(port=port)
            _check_child(self.parent)
            if not callable(getattr(self.parent, "_local_request", None)):
                raise RuntimeError(_INCOMPATIBLE)
            _install_memory_bridge(self.parent, _browser_assets())
            self.memory_bridge = True
        except (ImportError, AttributeError, OSError, ValueError) as error:
            raise RuntimeError(_INCOMPATIBLE) from error
        self._factory = WebRuntime
        self.parent.app.router.routes.remove(_check_routes(self.parent))

    def local_request(self, request):
        # Retain the pinned runtime's exact trusted loopback Host/peer policy.
        return self.parent._local_request(request)

    def new_bridge(self):
        child = self._factory()
        _check_child(child)
        # Never call start() on a child. Its public ASGI route and real browser
        # session work on the parent's socket only at this pinned runtime revision.
        child._origin = self.parent.origin
        child._running = True
        return child
