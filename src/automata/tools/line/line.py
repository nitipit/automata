#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["cyclopts>=4.23.3", "playwright>=1.63.0", "dictify>=5.0.2"]
# ///
"""Bounded LINE Chrome automation with isolated, workspace-owned reading state."""

import base64
import hashlib
import json
import os
import re
import shlex
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from cyclopts import App

# Resolve operational paths from the calling workspace, never from package/install source.
ROOT = Path.cwd().resolve()
PROFILE = (
    Path(os.environ.get("AUTOMATA_LINE_PROFILE", ROOT / ".agents/var/browser/line"))
    .expanduser()
    .resolve()
)
STATE = ROOT / ".agents/var/tools/line"
URL = "chrome-extension://ophjlpahpchlmihnnnihgmmeilfjmjjc/index.html"
ROOM = '[class*="chatroom-module__chatroom__"]'
HEADER = '[class*="chatroomHeader-module__button_name__"]'
PREVIEW = '[class*="pastedImageList-module__image_list_item__"]'
CHAT_ID = re.compile(r"[A-Za-z0-9_-]+")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def check_profile_scope():
    """Never mix consumers/tokens when a workspace selects another browser profile."""
    require(sys.platform == "linux", "This tool currently supports Linux only")
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")).expanduser().resolve()
    for personal in (
        config / "google-chrome",
        config / "chromium",
        config / "google-chrome-beta",
        config / "google-chrome-unstable",
    ):
        require(
            not PROFILE.is_relative_to(personal),
            "Personal/default Chrome profiles are not allowed; use an isolated profile",
        )
    scope = STATE / "profile.json"
    if scope.exists():
        try:
            stored = json.loads(scope.read_text())
        except (ValueError, OSError) as exc:
            raise RuntimeError("Cannot read profile scope; preserve state for inspection") from exc
        require(
            stored == {"version": 1, "profile": str(PROFILE)},
            "Workspace LINE state belongs to another profile; use a separate workspace",
        )


def bind_profile_scope():
    check_profile_scope()
    scope = STATE / "profile.json"
    if not scope.exists():
        # Called under the operation lock, only after a verified LINE page was found.
        from reading_state import atomic, json_bytes

        atomic(scope, json_bytes({"version": 1, "profile": str(PROFILE)}))


def profile_port():
    """Discover the debugging port only from the exact local isolated profile."""
    check_profile_scope()
    ports = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            args = (proc / "cmdline").read_bytes().split(b"\0")
            args = [a.decode() for a in args if a]
            # Chrome can rewrite argv into a single process-title string.
            if len(args) == 1:
                args = shlex.split(args[0])
            executable = (proc / "exe").resolve().name
            if (
                args
                and executable == "chrome"
                and f"--user-data-dir={PROFILE}" in args
                and not any(a.startswith("--type=") for a in args)
            ):
                require(
                    "--remote-debugging-address=127.0.0.1" in args,
                    "Expected loopback debugging address is missing",
                )
                ports.extend(
                    int(a.split("=", 1)[1])
                    for a in args
                    if a.startswith("--remote-debugging-port=")
                )
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    require(
        len(ports) == 1 and 0 < ports[0] < 65536,
        "Exactly one Chrome using the configured isolated profile is required",
    )
    return ports[0]


@contextmanager
def locked():
    check_profile_scope()
    import fcntl

    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (STATE / "operation.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def save_state(data):
    temp = STATE / "draft.tmp"
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(data, handle)
        handle.flush()
        os.fsync(handle.fileno())
    temp.replace(STATE / "draft.json")


def load_state():
    return json.loads((STATE / "draft.json").read_text())


def today_text(text):
    """LINE 3.7 renders latest-first, with the date marker AFTER its messages."""
    lines = text.splitlines()
    require("Today" in lines, "Today boundary not loaded; refusing to guess dates")
    return "\n".join(lines[: lines.index("Today")])


class Line:
    def __init__(self, page):
        self.page = page
        self.room = page.locator(ROOM)

    def chat(self):
        require(self.room.count() == 1, "Open a chat first")
        header = self.room.locator(HEADER)
        require(header.count() == 1, "Ambiguous chat header")
        return header.inner_text().splitlines()[0].strip()

    def chat_id(self):
        require(self.room.count() == 1, "Open a chat first")
        chat_id = self.room.get_attribute("data-mid")
        require(
            chat_id is not None and CHAT_ID.fullmatch(chat_id),
            "Active chat ID missing; stopped",
        )
        return chat_id

    def verify(self, chat_id, chat=None):
        require(CHAT_ID.fullmatch(chat_id or ""), "A stable chat ID is required")
        require(self.chat_id() == chat_id, "Wrong active chat ID; stopped")
        if chat is not None:
            require(self.chat() == chat, "Active chat name changed; stopped")

    def verify_name(self, chat):
        require(self.chat() == chat, "Wrong active chat; stopped")

    def open(self, chat):
        # Names are not globally unique; refuse multiple matching visible rows.
        names = self.page.get_by_text(chat, exact=True)
        rows = names.locator('xpath=ancestor::*[.//button[@aria-label="Go chatroom"]][1]')
        require(
            rows.count() == 1, "Chat not uniquely visible. Find it manually in LINE, then retry"
        )
        rows.get_by_role("link", name="Go chatroom").click()
        self.room.locator(HEADER).wait_for()
        self.verify_name(chat)

    def snapshot(self, chat_id, chat=None):
        self.verify(chat_id, chat)
        text = self.room.locator("textarea").input_value()
        images = self.room.locator(PREVIEW).evaluate_all("""es => es.map(e => ({
            name:e.title, src:e.querySelector('img')?.src
        }))""")
        mentions = self.room.locator('[part~="mention"]').evaluate_all(
            "es => es.map(e => e.outerHTML)"
        )
        value = {
            "chat": self.chat(),
            "chat_id": chat_id,
            "route": self.page.url,
            "text": text,
            "images": images,
            "mentions": mentions,
        }
        digest = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        return value, digest

    def empty(self, chat_id, chat=None):
        value, _ = self.snapshot(chat_id, chat)
        require(
            not value["text"] and not value["images"],
            "Existing draft found; refusing to overwrite or append",
        )

    def prepare(self, chat_id):
        value, digest = self.snapshot(chat_id)
        require(value["text"] or value["images"], "Composer is empty")
        state = {
            "token": str(uuid.uuid4()),
            "digest": digest,
            "status": "prepared",
            "chat_id": chat_id,
            "route": value["route"],
        }
        save_state(state)
        return {
            "status": "prepared",
            "chat": value["chat"],
            "chat_id": chat_id,
            "token": state["token"],
            "characters": len(value["text"]),
            "images": len(value["images"]),
        }

    def draft(self, chat_id, text, chat=None):
        require(
            text and len(text.encode("utf-16-le")) // 2 <= 10000,
            "Text must be nonempty and at most 10000 UTF-16 units",
        )
        self.empty(chat_id, chat)
        self.room.locator("textarea").fill(text)
        require(
            self.room.locator("textarea").input_value() == text,
            "Draft verification failed; inspect composer",
        )
        return self.prepare(chat_id)

    def mention(self, chat_id, member, text, chat=None):
        require(
            member.strip() and member != "All",
            "A named individual is required; @All is unsupported",
        )
        self.empty(chat_id, chat)
        editor = self.room.locator("textarea")
        editor.fill("@")
        options = self.page.get_by_role("option")
        options.first.wait_for()
        matches = options.filter(has=self.page.get_by_text(member, exact=True))
        require(matches.count() == 1, "Member missing or ambiguous; inspect draft, nothing sent")
        button = matches.locator("button[data-id]")
        require(
            button.count() == 1 and button.get_attribute("data-id"),
            "Individual member identity missing; stopped",
        )
        self.verify(chat_id, chat)
        button.click()
        marker = self.room.locator('[part~="mention"]')
        marker.wait_for(state="attached")
        require(marker.count() == 1, "Native mention marker not verified")
        # Preserve LINE custom-element mention metadata: never fill after selection.
        before = editor.input_value()
        if text:
            require(
                len((before + text).encode("utf-16-le")) // 2 <= 10000,
                "Mention plus text is too long",
            )
            editor.press("Control+End")
            editor.focus()
            self.page.keyboard.insert_text(text)
        require(
            editor.input_value() == before + text and marker.count() == 1,
            "Mention or suffix changed unexpectedly; inspect draft",
        )
        result = self.prepare(chat_id)
        result["mention"] = member
        return result

    def attach(self, chat_id, path, chat=None):
        data = path.read_bytes()
        require(data.startswith(b"\x89PNG\r\n\x1a\n"), "Only PNG images supported currently")
        self.empty(chat_id, chat)
        self.room.locator("textarea").evaluate(
            """(el, data) => {
          const file = new File([Uint8Array.from(atob(data.b64), c=>c.charCodeAt(0))],
                                data.name, {type:'image/png'});
          const dt = new DataTransfer(); dt.items.add(file);
          el.focus(); el.dispatchEvent(new ClipboardEvent('paste', {
            clipboardData:dt, bubbles:true, cancelable:true, composed:true
          }));
        }""",
            {"name": path.name, "b64": base64.b64encode(data).decode()},
        )
        self.room.locator(PREVIEW).wait_for()
        require(self.room.locator(PREVIEW).count() == 1, "Unexpected image count")
        require(
            self.room.locator(PREVIEW).get_attribute("title") == path.name,
            "Image preview filename mismatch",
        )
        return self.prepare(chat_id)

    def send(self, chat_id, token, chat=None):
        if isinstance(token, str) and token.startswith("sticker:"):
            return sticker_operations(self).send(chat_id, token, chat)
        state = load_state()
        require(
            state.get("token") == token and state.get("status") == "prepared",
            "Token missing, consumed, or uncertain; do not retry a send",
        )
        require(
            state.get("chat_id") == chat_id and isinstance(state.get("route"), str),
            "Token has no recipient identity binding; prepare a new draft",
        )
        require(
            self.page.url == state["route"],
            "LINE navigation changed since preparation; stopped",
        )
        value, digest = self.snapshot(chat_id, chat)
        require(digest == state["digest"], "Chat or draft changed; stopped")
        require(value["text"] or value["images"], "Empty draft")
        # Consume before dispatch. Crashes/timeouts must never authorize replay.
        state["status"] = "uncertain"
        save_state(state)
        self.verify(chat_id, chat)
        self.room.locator("textarea").press("Enter")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            current, _ = self.snapshot(chat_id, chat)
            if not current["text"] and not current["images"]:
                state["status"] = "dispatched"
                save_state(state)
                return {
                    "status": "dispatched",
                    "chat": value["chat"],
                    "chat_id": chat_id,
                    "delivery": (
                        "Composer cleared; server delivery/read receipt not verified. "
                        "Do not resend."
                    ),
                }
            self.page.wait_for_timeout(100)
        raise RuntimeError("Send outcome uncertain. Inspect LINE; never automatically retry")


app = App(
    name="line",
    help="""LINE via uv + Playwright, isolated Chrome only (Linux).

Run: uv run --script .agents/tools/line/line.py COMMAND. Script dependencies may
be fetched by uv; use --offline once cached. The tool itself never installs or
launches Chrome. Install the LINE Chrome extension and sign in yourself first.
Default profile: CWD/.agents/var/browser/line. Set AUTOMATA_LINE_PROFILE to an
explicit isolated profile path to override; personal/default profiles are refused.
Start Chrome with --user-data-dir=<absolute-profile-path>,
--remote-debugging-address=127.0.0.1 and --remote-debugging-port=<unused-port>.
No saved port or default-profile fallback is used. Open one LINE index page:
chrome-extension://ophjlpahpchlmihnnnihgmmeilfjmjjc/index.html

Draft tokens, sticker receipt, profile binding and reading checkpoints:
CWD/.agents/var/tools/line.
Paths are workspace-relative even when this tool is globally installed/symlinked.
A workspace is bound to one isolated profile after its first browser operation;
use a separate workspace for another profile. Never copy login/profile/state data.
collect appends private message text to its explicit output. read does not commit
checkpoints. Add output/state paths to Git ignore before collecting. Read commands
may mark chats read and move the UI. Draft commands never send; send needs explicit
recipient/content authorization and a prepared token. Never retry an uncertain send.
No automatic cleanup: deleting draft/reading state loses recovery and may replay.

AUTOMATA_LINE_TIMEZONE controls output times and --during windows (default UTC).
Disconnects on exit; Chrome remains open. Names are display hints only, never recipient
authority. Draft and send commands require the stable --chat-id returned by chats while
that same chat is active; an optional --chat only verifies its display name. The old
name-only --chat contract is intentionally rejected. Use draft-mention for one native
mention; @All is unsupported. sticker-catalog inspects metadata; prepare-sticker never
clicks a sticker. send accepts the returned sticker token only with explicit permission.
Uncertain sticker receipts block fresh sticker preparation; cleanup is not rollback.
""",
)


@app.command
def status():
    """Verify profile and LINE without reading messages."""
    execute("status")


@app.command
def open_chat(*, chat: str):
    """Open an exact visible chat (may mark messages read).

    Parameters
    ----------
    chat
        Exact unique visible chat name.
    """
    execute("open-chat", chat=chat)


@app.command
def read_today(*, chat: str):
    """Read loaded today text, latest-first; not a complete archive.

    Parameters
    ----------
    chat
        Exact chat name; must already be active.
    """
    execute("read-today", chat=chat)


@app.command
def draft_text(*, chat_id: str, text: str, chat: str | None = None):
    """Fill an empty composer without sending, bound to a stable chat ID.

    Parameters
    ----------
    chat_id
        Stable ID returned by chats; the matching chat must already be active.
    chat
        Optional display-name hint; it is verified but never used as authority.
    text
        Exact text including newlines. @Name is plain text, not a mention.
    """
    execute("draft-text", chat_id=chat_id, chat=chat, text=text)


@app.command
def draft_mention(*, chat_id: str, member: str, text: str = "", chat: str | None = None):
    """Prepare one native mention, bound to a stable chat ID; never send.

    Parameters
    ----------
    chat_id
        Stable ID returned by chats; the matching chat must already be active.
    chat
        Optional display-name hint; it is verified but never used as authority.
    member
        Exact unique name in LINE's member picker. All is unsupported.
    text
        Optional text following the mention; newlines and emoji supported.
    """
    execute("draft-mention", chat_id=chat_id, chat=chat, member=member, text=text)


@app.command
def attach_image(*, chat_id: str, file: Path, chat: str | None = None):
    """Paste a PNG into an empty composer without sending, bound to a stable chat ID.

    Parameters
    ----------
    chat_id
        Stable ID returned by chats; the matching chat must already be active.
    chat
        Optional display-name hint; it is verified but never used as authority.
    file
        Existing local PNG path.
    """
    execute("attach-image", chat_id=chat_id, chat=chat, file=file)


def sticker_operations(line):
    from sticker_api import StickerOperations, verified_picker

    return StickerOperations(line, STATE, verified_picker)


@app.command
def sticker_catalog(
    *, chat_id: str, package_id: str | None = None, limit: int = 100, chat: str | None = None
):
    """Inspect bounded sticker metadata without clicking any sticker or sending.

    Requires the exact active chat and an empty composer. Stops if the live
    sticker UI adapter is not validated. Returned coverage is not a full catalog.
    """
    execute("sticker-catalog", chat_id=chat_id, package_id=package_id, limit=limit, chat=chat)


@app.command
def prepare_sticker(*, chat_id: str, package_id: str, sticker_id: str, chat: str | None = None):
    """Prepare a recipient/sticker-bound metadata token; never click a sticker.

    Select stable IDs from sticker-catalog. An uncertain sticker receipt blocks
    new sticker preparation; never delete it to bypass reconciliation.
    """
    execute(
        "prepare-sticker", chat_id=chat_id, package_id=package_id, sticker_id=sticker_id, chat=chat
    )


@app.command
def send(*, chat_id: str, token: str, chat: str | None = None):
    """Send a prepared draft once, only with explicit authorization and stable ID.

    Parameters
    ----------
    chat_id
        Stable ID bound into the preparation token; the matching chat must be active.
    chat
        Optional display-name hint; it is verified but never used as authority.
    token
        Token from a draft command; consumed before dispatch.
    """
    execute("send", chat_id=chat_id, chat=chat, token=token)


def reading_command(command, **kwargs):
    # Import only for new commands; existing draft/send invocations keep their dependencies.
    from types import SimpleNamespace

    import reading_api

    runtime = SimpleNamespace(
        STATE=STATE,
        locked=locked,
        profile_port=profile_port,
        URL=URL,
        HEADER=HEADER,
        Line=Line,
        bind_profile_scope=bind_profile_scope,
    )
    result = reading_api.dispatch(runtime, command, kwargs)
    print(json.dumps({"api_version": 1, "ok": True, "result": result}, ensure_ascii=False))


@app.command
def chats(*, search: str = ""):
    """List chat IDs as JSON; scan virtualized list without using unread flags as progress.

    Parameters
    ----------
    search
        Optional case-insensitive substring, matched locally without editing LINE search.
    """
    reading_command("chats", search=search)


@app.command
def read(
    *,
    chat_id: str,
    since: str | None = None,
    unseen: bool = False,
    consumer: str = "journal",
    limit: int = 100,
    max_scrolls: int = 10,
    before: str | None = None,
):
    """Read structured messages as JSON, newest-first; never save or advance reading state.

    Opens the target chat (may mark read); refuses an existing draft or active search.
    Reports missing checkpoints, bounded history, and uninspected attachments.
    Invoke through uv run --script to resolve the declared dependencies.

    Parameters
    ----------
    chat_id
        Exact stable chat ID from chats, not a display name.
    since
        Inclusive ISO timestamp with timezone. Unseen defaults to the consumer's
        initial window or 24 hours; plain read has no date filter.
    unseen
        Exclude IDs/content already saved by this consumer, independently of LINE read badges.
    consumer
        Reading namespace (letters/digits/_/-), default journal.
    limit
        Maximum messages returned, 1..1000; coverage.more reports additional observed matches.
    max_scrolls
        Maximum older-history scroll attempts, 0..100; no guarantee of complete history.
    before
        Exclusive timestamp_ms:message_id cursor from next_before to page older matches.
    """
    reading_command(
        "read",
        chat_id=chat_id,
        since=since,
        unseen=unseen,
        consumer=consumer,
        limit=limit,
        max_scrolls=max_scrolls,
        before=before,
    )


@app.command
def collect(
    *,
    all: bool = False,
    chat_id: str | None = None,
    consumer: str = "journal",
    output: Path = ROOT / "LINE.md",
    since: str | None = None,
    limit: int = 100,
    max_scrolls: int = 10,
    max_chats: int = 200,
    during: str | None = None,
):
    """Append unseen messages, then commit per-consumer checkpoints; no sending or summary.

    Select --all OR --chat-id. Existing output is preserved. Consumer binds to one
    output path. Interrupted writes are reconciled by hashes on the next collect;
    changed output blocks recovery, never blindly overwrites. Uses the LINE lock.
    Reading state: .agents/var/tools/line/reading/CONSUMER/. Remove only with explicit
    authorization; deleting checkpoints causes replay. Timer scheduling is separate.

    Parameters
    ----------
    all
        Inspect all listed chats, irrespective of mobile reads or notification badges.
    chat_id
        Inspect one exact chat ID instead of --all.
    consumer
        Independent reading-state namespace, default journal.
    output
        Private append-only Markdown journal; default workspace LINE.md. Do not edit
        previously checkpointed content; manual appends are allowed. Exclude from Git.
    since
        Initial window for new chats: timezone-qualified ISO timestamp; default 24h ago.
        Existing chat checkpoints keep their original window.
    limit
        Per-chat message batch, 1..1000. Saves oldest new messages first; reports backlog.
    max_scrolls
        Per-chat older-history scroll bound, 0..100. Missing history is reported.
    max_chats
        Chat count bound, 1..1000; oldest checked first; overall collection bounded to 8 min.
    during
        Optional HH:MM-HH:MM in AUTOMATA_LINE_TIMEZONE (UTC by default).
        Outside the window exits without checking. Runs once and exits; scheduling
        belongs to an explicitly authorized timer, not this tool.
    """
    reading_command(
        "collect",
        all=all,
        chat_id=chat_id,
        consumer=consumer,
        output=output,
        since=since,
        limit=limit,
        max_scrolls=max_scrolls,
        max_chats=max_chats,
        during=during,
    )


@app.command
def state(*, consumer: str = "journal"):
    """Inspect checkpoint counts, anchors, coverage and pending recovery without opening Chrome.

    Parameters
    ----------
    consumer
        Reading-state namespace to inspect; does not create checkpoints or recover writes.
    """
    reading_command("state", consumer=consumer)


def execute(command, **kwargs):
    args = SimpleNamespace(command=command, **kwargs)
    from playwright.sync_api import sync_playwright

    with locked(), sync_playwright() as p:
        port = profile_port()
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        pages = [
            page
            for context in browser.contexts
            for page in context.pages
            if page.url.split("#", 1)[0] == URL
        ]
        require(len(pages) == 1, "Open exactly one LINE extension index page")
        page = pages[0]
        bind_profile_scope()
        page.set_default_timeout(5000)
        line = Line(page)
        if args.command == "status":
            output = {
                "status": "connected",
                "profile": str(PROFILE),
                "chat": line.chat() if line.room.count() else None,
            }
        elif args.command == "open-chat":
            line.open(args.chat)
            output = {"status": "opened", "chat": args.chat}
        elif args.command == "read-today":
            line.verify_name(args.chat)
            output = {
                "chat": args.chat,
                "local_time": datetime.now().astimezone().isoformat(),
                "coverage": "Loaded text only, latest-first; not all messages or attachments",
                "text": today_text(line.room.inner_text()),
            }
        elif args.command == "draft-text":
            output = line.draft(args.chat_id, args.text, args.chat)
        elif args.command == "draft-mention":
            output = line.mention(args.chat_id, args.member, args.text, args.chat)
        elif args.command == "attach-image":
            output = line.attach(args.chat_id, args.file, args.chat)
        elif args.command == "sticker-catalog":
            output = sticker_operations(line).inspect(
                args.chat_id, args.package_id, args.limit, args.chat
            )
        elif args.command == "prepare-sticker":
            output = sticker_operations(line).prepare(
                args.chat_id, args.package_id, args.sticker_id, args.chat
            )
        else:
            output = line.send(args.chat_id, args.token, args.chat)
        print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    try:
        app(exit_on_error=False, print_error=False)
    except Exception as exc:
        code = getattr(
            exc,
            "code",
            "INVALID_ARGUMENT"
            if type(exc).__module__.startswith("cyclopts")
            else "BUSY"
            if isinstance(exc, BlockingIOError)
            else "LINE_ERROR",
        )
        print(
            json.dumps(
                {
                    "api_version": 1,
                    "ok": False,
                    "code": code,
                    "error": str(exc),
                    "details": getattr(exc, "details", {}),
                    "retry_send": False,
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(2 if code == "INVALID_ARGUMENT" else 1)
