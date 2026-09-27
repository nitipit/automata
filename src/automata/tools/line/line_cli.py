#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["cyclopts>=4.23.3", "playwright>=1.63.0", "dictify>=5.0.2"]
# ///
"""Discoverable LINE commands for agent users; no legacy command aliases."""

import json
import sys
from typing import Annotated

from cyclopts import App, Parameter
from dictify import Model
from line_schemas import Chat, Chats, Read, Send, Stickers, cursor_key, date_ms

app = App(
    name="line",
    help=(
        "LINE Chrome extension control using an already-running isolated profile.\n\n"
        "Linux; AUTOMATA_LINE_PROFILE defaults to CWD/.agents/var/browser/line. "
        "Chrome requires --remote-debugging-address=127.0.0.1 and "
        "--remote-debugging-port=PORT; open "
        "chrome-extension://ophjlpahpchlmihnnnihgmmeilfjmjjc/index.html.\n\n"
        "JSON results/errors. Private receipts: CWD/.agents/var/tools/line. "
        "No automatic login, sending retries, or state cleanup."
    ),
)


def emit(result):
    print(json.dumps({"api_version": 1, "ok": True, "result": result}, ensure_ascii=False))


def reader(line):
    from line_runtime import HEADER, URL
    from reading_api import Reader

    return Reader(line, URL, HEADER)


@app.command
def status():
    """Verify profile and LINE without reading messages."""
    from line_runtime import PROFILE, connect

    with connect() as line:
        emit(
            {
                "status": "connected",
                "profile": str(PROFILE),
                "chat_id": line.chat_id() if line.room.count() else None,
            }
        )


@app.command
def chats(options: Annotated[Chats | None, Parameter(name="*")] = None):
    """List stable chat IDs without reading chat history."""
    from line_runtime import connect

    with connect() as line, reader(line).preserved() as view:
        emit(view.chats((options or Chats()).search))


@app.command
def open_chat(options: Annotated[Chat, Parameter(name="*")]):
    """Open an exact chat ID; may mark messages read."""
    from line_runtime import connect

    with connect() as line:
        view = reader(line)
        # Check search/draft ownership, but deliberately retain the requested navigation.
        with view.preserved(restore=False):
            name = view.open_id(options.chat_id)
        emit({"status": "opened", "chat": {"id": options.chat_id, "name": name}})


@app.command
def read(options: Annotated[Read, Parameter(name="*")]):
    """Read bounded history; never save messages. May mark messages read.

    Newest-first, except --after is oldest-first. Dates use AUTOMATA_LINE_TIMEZONE
    (UTC default); timestamps require offsets. Inspect coverage before continuing.
    """
    from line_runtime import connect

    with connect() as line, reader(line).preserved() as view:
        result = view.read(
            options.chat_id,
            {},
            date_ms(options.since),
            unseen=False,
            limit=options.limit,
            max_scrolls=options.max_scrolls,
            before=cursor_key(options.before),
            newest_first=not options.after,
            after=cursor_key(options.after),
            until_ms=date_ms(options.until),
        )
        result.pop("anchor_candidate", None)
        messages = result["messages"]
        for message in messages:
            message.pop("fingerprint", None)
            message.pop("change", None)

        def key(message):
            return message["timestamp_ms"], message["id"]

        def encode(message):
            return f"{message['timestamp_ms']}:{message['id']}"

        result["next_before"] = encode(min(messages, key=key)) if messages else None
        result["next_after"] = encode(max(messages, key=key)) if messages else None
        result["order"] = "oldest-first" if options.after else "newest-first"
        result["checkpoints_changed"] = False
        emit(result)


@app.command
def stickers(options: Annotated[Stickers, Parameter(name="*")]):
    """Inspect sticker IDs in the active chat. Never click tiles to preview; clicks can send."""
    from line_runtime import connect
    from line_send import sticker_operations

    with connect() as line:
        emit(sticker_operations(line).inspect(options.chat_id, options.package_id, options.limit))


def dispatch_send(line, options):
    """Shared preparation for direct sends and drafts; same one-shot confirmation path."""
    from line_send import sticker_operations

    if options.confirm:
        return line.send(options.chat_id, options.confirm)
    if options.sticker_id:
        prepared = sticker_operations(line).prepare(
            options.chat_id, options.sticker_package, options.sticker_id
        )
    elif options.image:
        prepared = line.attach(options.chat_id, options.image)
    elif options.mention:
        prepared = line.mention(options.chat_id, options.mention, options.text or "")
    else:
        prepared = line.draft(options.chat_id, options.text)
    return prepared if options.draft else line.send(options.chat_id, prepared["token"])


@app.command
def send(options: Annotated[Send, Parameter(name="*")]):
    """Send content to the active chat, or prepare with --draft and later --confirm TOKEN.

    Requires an empty composer for new content; failure may leave a partial draft.
    Consumes confirmation before dispatch. Never retry an uncertain send.
    Sticker drafts are metadata-only. Success is not recipient delivery confirmation.
    """
    from line_runtime import connect

    with connect() as line:
        emit(dispatch_send(line, options))


def main():
    try:
        app(exit_on_error=False, print_error=False)
    except Exception as exc:
        invalid = isinstance(exc, (ValueError, Model.Error)) or type(exc).__module__.startswith(
            "cyclopts"
        )
        code = getattr(
            exc,
            "code",
            "INVALID_ARGUMENT"
            if invalid
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
        raise SystemExit(2 if code == "INVALID_ARGUMENT" else 1) from None


if __name__ == "__main__":
    main()
