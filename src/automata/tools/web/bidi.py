"""Connect only to a profile-matched local Firefox WebDriver BiDi endpoint."""

import fcntl
import http.client
import json
import os
import re
import shutil
import stat
import subprocess
import time
from contextlib import suppress
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit

from .browser import BrowserError, _existing_profile
from .config import _config_home

_START_SECONDS = 10
_WIRE_SECONDS = 3
_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,128}")


class BiDiError(BrowserError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _locked(profile):
    """Check Firefox's Linux advisory profile lock without creating/removing it."""
    try:
        fd = os.open(profile / ".parentlock", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return False
    with os.fdopen(fd, "rb") as lock:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
            raise ValueError
        try:
            fcntl.lockf(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        return False


def _port(profile):
    fd = os.open(profile / "WebDriverBiDiServer.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as note:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_size > 4096:
            raise ValueError
        endpoint = json.loads(note.read(4097))
    port = endpoint["ws_port"]
    if endpoint["ws_host"] != "127.0.0.1" or type(port) is not int or not 0 < port <= 65535:
        raise ValueError
    return port


def _listener_pid(ss, port):
    listing = subprocess.run(
        [ss, "-H", "-ltnp", f"sport = :{port}"],
        check=True,
        capture_output=True,
        text=True,
        timeout=1,
    ).stdout.splitlines()
    if len(listing) != 1 or listing[0].split()[3] != f"127.0.0.1:{port}":
        raise ValueError
    pids = set(re.findall(r"\bpid=(\d+),", listing[0]))
    if len(pids) != 1:
        raise ValueError
    return int(pids.pop())


def _process_identity(pid, target):
    proc = Path("/proc") / str(pid)
    # Some distro launchers (including Fedora's) are scripts that exec Firefox.
    launcher = target.executable.resolve(strict=True)
    prefix = launcher.parent.parent
    allowed = {launcher, *(prefix / lib / "firefox" / "firefox" for lib in ("lib", "lib64"))}
    if proc.stat().st_uid != os.geteuid() or (proc / "exe").resolve(strict=True) not in allowed:
        raise ValueError
    args = (proc / "cmdline").read_bytes().split(b"\0")
    profiles = [args[i + 1] for i, arg in enumerate(args[:-1]) if arg == b"--profile"]
    if profiles != [os.fsencode(target.profile)]:
        raise ValueError
    # /proc/PID/stat field 22 (start time); the command name can include spaces.
    return (proc / "stat").read_bytes().rsplit(b")", 1)[1].split()[19]


def _cold_start(target):
    env = os.environ.copy()
    for name in ("XRE_PROFILE_PATH", "XRE_PROFILE_LOCAL_PATH", "MOZ_NO_REMOTE", "MOZ_NEW_INSTANCE"):
        env.pop(name, None)
    return subprocess.Popen(
        [
            str(target.executable),
            "--profile",
            str(target.profile),
            "--no-remote",
            "--remote-debugging-port=0",
            "about:blank",
        ],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _endpoint(target, ss, process=None):
    port = _port(target.profile)
    pid = _listener_pid(ss, port)
    if process is not None and pid != process.pid:
        raise ValueError
    return port, pid, _process_identity(pid, target)


def _wait_for_owned_endpoint(target, ss, process):
    deadline = time.monotonic() + _START_SECONDS
    while time.monotonic() < deadline and process.poll() is None:
        try:
            return _endpoint(target, ss, process)
        except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError):
            time.sleep(0.05)  # Readiness only; never relaunch or attach to a different PID.
    raise BiDiError("firefox_bidi_start_unconfirmed")


def connect_firefox(target):
    """Reuse verified control, or cold-start only an unlocked dedicated profile."""
    try:
        import websocket
    except ImportError:
        raise BiDiError("websocket_client_unavailable") from None
    if not callable(getattr(websocket, "create_connection", None)):
        raise BiDiError("websocket_client_unavailable")
    ss = shutil.which("ss")
    if ss is None or not Path("/proc/self").is_dir():
        raise BiDiError("firefox_bidi_verification_unavailable")
    browser = None
    try:
        profile = _existing_profile(target.profile)
        # An explicit custom location must be a dedicated profile, not one of
        # Firefox's normal personal-profile stores (including symlink aliases).
        ordinary = (
            Path.home() / ".mozilla",
            _config_home() / "mozilla",
            Path.home() / ".var/app/org.mozilla.firefox",
            Path.home() / "snap/firefox",
        )
        if (
            profile != target.profile
            or profile.stat().st_uid != os.geteuid()
            or any(profile.is_relative_to(root.resolve()) for root in ordinary)
        ):
            raise BiDiError("firefox_profile_not_dedicated")
        if _locked(profile):
            endpoint = _endpoint(target, ss)
        else:
            endpoint = _wait_for_owned_endpoint(target, ss, _cold_start(target))
        port, pid, _ = endpoint
        socket = websocket.create_connection(
            f"ws://127.0.0.1:{port}/session",
            suppress_origin=True,
            timeout=_WIRE_SECONDS,
            http_no_proxy=["127.0.0.1"],
            header={"User-Agent": "Automata/1.0"},
        )
        browser = FirefoxBiDi(socket)
        if _endpoint(target, ss) != endpoint or not _locked(profile):
            raise ValueError
        created = browser.call("session.new", capabilities={})
        browser.active = True
        caps = created["capabilities"]
        if (
            caps["browserName"] != "firefox"
            or caps["moz:processID"] != pid
            or caps["moz:profile"] != str(profile)
        ):
            raise ValueError
        return browser
    except BiDiError:
        if browser is not None:
            browser.close()
        raise
    except Exception:
        if browser is not None:
            browser.close()
        raise BiDiError("firefox_bidi_unavailable") from None


def _redeem(admission, origin, path):
    """Consume the existing launch ticket without navigating to a private URL."""
    ticket_path = urlsplit(admission.url).path
    prefix = path + "#admission="
    client = http.client.HTTPConnection("127.0.0.1", urlsplit(origin).port, timeout=_WIRE_SECONDS)
    try:
        client.request("GET", ticket_path, headers={"User-Agent": "Automata/1.0"})
        with client.getresponse() as response:
            location = response.getheader("Location", "")
            token = location.removeprefix(prefix)
            if (
                response.status != 303
                or not location.startswith(prefix)
                or not _TOKEN.fullmatch(token)
            ):
                raise BrowserError("The private Firefox handoff was refused")
            return token
    finally:
        client.close()


class FirefoxBiDi:
    def __init__(self, socket):
        self.socket = socket
        self.sequence = 0
        self.active = False
        self.context = self.expected_url = None
        self._wire = Lock()

    def call(self, method, **params):
        # A cancelled asyncio wait can leave the bounded worker call in flight.
        # Serialize session.end with it so neither call consumes the other's reply.
        with self._wire:
            self.sequence += 1
            command = {"id": self.sequence, "method": method, "params": params}
            deadline = time.monotonic() + _WIRE_SECONDS
            self.socket.settimeout(_WIRE_SECONDS)
            self.socket.send(json.dumps(command))
            while (remaining := deadline - time.monotonic()) > 0:
                self.socket.settimeout(remaining)
                reply = json.loads(self.socket.recv())
                if reply.get("id") == command["id"]:
                    if reply["type"] == "success":
                        return reply["result"]
                    break
        raise BrowserError("Firefox did not confirm a BiDi command")

    def open_chat(self, admission, origin):
        """Open exactly one new context at the clean canonical URL, scoped to its ID."""
        path = f"/chat/sessions/{admission.session_id}/"
        self.expected_url = origin + path
        try:
            self.context = self.call("browsingContext.create", type="tab")["context"]
            token = _redeem(admission, origin, path)
            # The chat already consumes and deletes this document-local handoff.
            # Never navigate to the ticket or insert the reconnect key into URL/history.
            preload = self.call(
                "script.addPreloadScript",
                contexts=[self.context],
                functionDeclaration=(
                    f"() => {{ if (location.href === {json.dumps(self.expected_url)}) "
                    f"window.__automataChatAdmission = {json.dumps(token)}; }}"
                ),
            )["script"]
            try:
                self.call(
                    "browsingContext.navigate",
                    context=self.context,
                    url=self.expected_url,
                    wait="interactive",
                )
                if self._evaluate("location.href") != self.expected_url:
                    raise ValueError
            finally:
                self.call("script.removePreloadScript", script=preload)
        except Exception:
            raise BrowserError("Firefox chat navigation was not confirmed") from None

    def _evaluate(self, expression):
        reply = self.call(
            "script.evaluate",
            expression=expression,
            target={"context": self.context},
            awaitPromise=False,
        )
        if reply["type"] != "success":
            raise ValueError
        return reply["result"].get("value")

    def chat_ready(self):
        try:
            return (
                self._evaluate(
                    f"location.href === {json.dumps(self.expected_url)} && "
                    "document.querySelector('#connection-status')?.textContent === 'Connected'"
                )
                is True
            )
        except Exception:
            raise BrowserError("Firefox chat target is not verifiable") from None

    def close(self):
        # Never close a tab, stop the browser, or end another controller's session.
        if self.active:
            with suppress(Exception):
                self.call("session.end")
        with suppress(Exception):
            self.socket.close(timeout=0.5)
