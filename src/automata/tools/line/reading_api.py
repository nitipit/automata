"""Single-shot, bounded LINE readers used by the public line.py commands."""

import os
import re
import time
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from reading_state import ApiError, ReadingStore, atomic, digest, ensure, json_bytes

TIMEZONE = os.environ.get("AUTOMATA_LINE_TIMEZONE", "UTC")
TZ = ZoneInfo(TIMEZONE)
ROW = '[class*="chatlistItem-module__chatlist_item__"]'
MESSAGE = "[data-message-select-id]"


def now_iso():
    return datetime.now(TZ).isoformat(timespec="seconds")


def parse_since(value):
    if value is None:
        return None
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        ensure(date.tzinfo is not None, "INVALID_ARGUMENT", "Since needs an explicit timezone")
        return int(date.timestamp() * 1000)
    except ValueError as exc:
        raise ApiError("INVALID_ARGUMENT", "Since must be an ISO date-time with timezone") from exc


def in_window(window, now=None):
    if not window:
        return True
    ensure(
        re.fullmatch(r"\d{2}:\d{2}-\d{2}:\d{2}", window),
        "INVALID_ARGUMENT",
        "During must be HH:MM-HH:MM in the configured timezone",
    )
    begin, end = window.split("-")
    for value in (begin, end):
        h, m = map(int, value.split(":"))
        ensure(h < 24 and m < 60, "INVALID_ARGUMENT", "Invalid clock time")
    ensure(begin < end, "INVALID_ARGUMENT", "Window must start before end on the same day")
    return begin <= (now or datetime.now(TZ)).strftime("%H:%M") < end


def select_messages(
    messages,
    entry,
    since_ms,
    unseen,
    limit,
    before=None,
    newest_first=False,
    after=None,
    until_ms=None,
):
    """Equal timestamps never collapse messages. Cursor is the (timestamp, ID) tuple."""
    selected = []
    for message in sorted(messages, key=lambda m: (m["timestamp_ms"], m["id"])):
        if since_ms is not None and message["timestamp_ms"] < since_ms:
            continue
        if until_ms is not None and message["timestamp_ms"] >= until_ms:
            continue
        if before and (message["timestamp_ms"], message["id"]) >= tuple(before):
            continue
        if after and (message["timestamp_ms"], message["id"]) <= tuple(after):
            continue
        old = entry.get("seen", {}).get(message["id"])
        fingerprint = digest(
            json_bytes({k: v for k, v in message.items() if k not in ("timestamp", "sender")})
        )
        if unseen and old and old["fingerprint"] == fingerprint:
            continue
        selected.append(dict(message, fingerprint=fingerprint, change="edited" if old else "new"))
    # Newest-first pages support repeated --before; collect uses oldest-first to drain backlog.
    if newest_first:
        selected.reverse()
    return selected[:limit], len(selected) > limit


class Reader:
    def __init__(self, line, url, header):
        self.line, self.page = line, line.page
        self.base, self.header = url, header
        self.owned_url = self.page.url

    def guard(self):
        ensure(
            self.page.url == self.owned_url, "UI_CHANGED", "User changed the active chat; stopped"
        )
        if self.line.room.count():
            editor = self.line.room.locator("textarea")
            ensure(
                not editor.count() or not editor.input_value(),
                "DRAFT_PRESENT",
                "Composer has a draft; no navigation or overwrite",
            )
            ensure(
                not self.line.room.locator(
                    '[class*="pastedImageList-module__image_list_item__"]'
                ).count()
                and not self.line.room.locator('[part~="mention"]').count(),
                "DRAFT_PRESENT",
                "Composer has an attachment or mention",
            )

    @contextmanager
    def preserved(self, restore=True):
        original = self.page.url
        self.guard()
        search = self.page.get_by_placeholder("Search chat list")
        ensure(
            search.count() == 1 and not search.input_value(),
            "UI_BUSY",
            "Clear the chat-list search before automated reading",
        )
        try:
            yield self
        finally:
            # No global input. Restore only while the known chat and empty draft are still ours.
            if restore and self.page.url == self.owned_url and original != self.page.url:
                try:
                    self.guard()
                    self.page.goto(original)
                    self.owned_url = original
                except Exception:
                    pass

    def chats(self, search="", max_scrolls=300):
        self.guard()
        rows = self.page.locator(ROW)
        ensure(rows.count() > 0, "UI_NOT_READY", "Chat list not loaded or LINE is logged out")
        scroller = rows.first.evaluate_handle("""e=>{
          for(let p=e.parentElement;p;p=p.parentElement)
            if(['auto','scroll'].includes(getComputedStyle(p).overflowY)
               && p.clientHeight>0) return p;
          return null;
        }""")
        ensure(scroller.evaluate("(e)=>!!e"), "UI_CHANGED", "Chat-list scroller unavailable")
        scroll = scroller.evaluate("(e)=>e.scrollTop")
        result, complete = {}, False
        try:
            scroller.evaluate("(e)=>e.scrollTop=0")
            for _ in range(max_scrolls):
                self.guard()
                self.page.wait_for_timeout(120)
                for row in rows.evaluate_all("""es=>es.map(e=>({
                  id:e.dataset.mid,name:e.querySelector('strong pre')?.innerText,
                  latest_ms:Date.parse(e.querySelector('time')?.getAttribute('datetime'))||null,
                  unread_badge:e.querySelector('[class*="message_count__"]')?.innerText||null
                }))"""):
                    ensure(row["id"] and row["name"], "UI_CHANGED", "Chat identity missing")
                    result[row["id"]] = row
                if scroller.evaluate("(e)=>e.scrollTop+e.clientHeight>=e.scrollHeight-2"):
                    complete = True
                    break
                scroller.evaluate("(e)=>e.scrollTop+=e.clientHeight*.8")
        finally:
            scroller.evaluate("(e,v)=>e.scrollTop=v", scroll)
        return {
            "chats": [v for v in result.values() if search.casefold() in v["name"].casefold()],
            "coverage": {"list_complete": complete, "entries_scanned": len(result)},
        }

    def open_id(self, chat_id):
        ensure(re.fullmatch(r"[A-Za-z0-9_-]+", chat_id), "INVALID_ARGUMENT", "Invalid chat ID")
        self.guard()
        target = self.base + "#/chats/" + chat_id
        if self.page.url != target:
            self.page.goto(target)
            self.owned_url = target
        from playwright.sync_api import TimeoutError as BrowserTimeout

        try:
            self.line.room.locator(self.header).wait_for()
        except BrowserTimeout as exc:
            raise ApiError(
                "CHAT_UNAVAILABLE",
                "Chat header did not load; no message checkpoint advanced",
                chat_id=chat_id,
            ) from exc
        ensure(
            self.line.room.get_attribute("data-mid") == chat_id,
            "CHAT_NOT_FOUND",
            "Active chat does not match requested ID",
        )
        self.guard()
        return self.line.chat()

    def extract(self, chat_id):
        self.guard()
        ensure(
            self.line.room.get_attribute("data-mid") == chat_id,
            "UI_CHANGED",
            "Chat identity changed",
        )
        raw = self.line.room.locator(MESSAGE).evaluate_all("""es=>es.filter(e=>
          !e.matches('[class*="messageDate-module__"]')).map(e=>{
          const text=e.querySelector('[class*="textMessageContent-module__text__"]');
          const content=e.querySelector('[class*="message-module__content_inner__"]');
          const c=content?.innerHTML||'';
          let kind=text?'text':c.includes('imageMessageContent')?'image':
            c.includes('stickerMessageContent')?'sticker':c.includes('videoMessageContent')?'video':
            c.includes('fileMessageContent')?'file':c.includes('audioMessageContent')?'audio':'unsupported';
          const plain=n=>{if(!n)return '';const x=n.cloneNode(true);
            x.querySelectorAll('img[alt]').forEach(i=>i.replaceWith(i.alt));return x.textContent;};
          return {id:e.dataset.messageSelectId,timestamp_ms:Number(e.dataset.timestamp),
            sender_id:e.dataset.mid||null,sender:plain(e.querySelector('[class*="username-module__"]'))||null,
            direction:e.dataset.direction||null,kind,
            text:text?plain(text):(e.dataset.messageContent||null),
            attachment_ids:[...e.querySelectorAll('[data-message-id]')].map(x=>x.dataset.messageId),
            truncated:!!e.querySelector('button[class*="more"]')};
        })""")
        for message in raw:
            ensure(
                isinstance(message["id"], str)
                and message["id"]
                and not message["id"].endswith("-")
                and type(message["timestamp_ms"]) is int
                and message["timestamp_ms"] > 0,
                "MESSAGE_ID_MISSING",
                "Message ID/timestamp unavailable; refusing a guessed checkpoint",
            )
            message["timestamp"] = datetime.fromtimestamp(
                message["timestamp_ms"] / 1000, TZ
            ).isoformat()
        return raw

    def read(
        self,
        chat_id,
        entry,
        since_ms,
        unseen=True,
        limit=100,
        max_scrolls=10,
        before=None,
        newest_first=False,
        after=None,
        until_ms=None,
    ):
        name = self.open_id(chat_id)
        log = self.line.room.locator(".message_list")
        ensure(log.count() == 1, "UI_CHANGED", "Message list unavailable")
        original_scroll = log.evaluate("(e)=>e.scrollTop")
        # Always start at newest, independent of what mobile or desktop has marked read.
        reverse = log.evaluate('(e)=>getComputedStyle(e).flexDirection=="column-reverse"')
        log.evaluate("(e,r)=>e.scrollTop=r?0:e.scrollHeight", reverse)
        anchor = entry.get("anchor_id", "")
        messages, stalled, previous_ids = {}, 0, None
        reached, reason = False, "scroll_limit"
        try:
            for _ in range(max_scrolls + 1):
                self.page.wait_for_timeout(350)
                batch = self.extract(chat_id)
                messages.update({m["id"]: m for m in batch})
                anchor_found = bool(anchor and anchor in messages)
                boundary = bool(
                    since_ms is not None
                    and messages
                    and min(m["timestamp_ms"] for m in messages.values()) < since_ms
                )
                # Incremental reads require the old anchor, even past a date boundary.
                if anchor_found if anchor else boundary:
                    reached, reason = (
                        True,
                        "checkpoint_found" if anchor else "since_boundary_reached",
                    )
                    break
                ids = set(messages)
                stalled = stalled + 1 if ids == previous_ids else 0
                previous_ids = ids
                if stalled >= 3:
                    reason = "no_more_loaded_messages"
                    break
                log.evaluate("(e,r)=>e.scrollTop=r?-e.scrollHeight:0", reverse)
        finally:
            if self.page.url == self.owned_url:
                log.evaluate("(e,v)=>e.scrollTop=v", original_scroll)
        selected, more = select_messages(
            list(messages.values()),
            entry,
            since_ms,
            unseen,
            limit,
            before,
            newest_first,
            after,
            until_ms,
        )
        coverage = {
            "boundary_reached": reached,
            "reason": reason,
            "checkpoint_found": bool(anchor and anchor in messages),
            "history_gap": bool(anchor and anchor not in messages),
            "older_history_unverified": not reached,
            "loaded_messages": len(messages),
            "more": more,
            "attachments_reviewed": False,
        }
        cursor = after or before
        if cursor:
            coverage["cursor_found"] = any(
                (m["timestamp_ms"], m["id"]) == tuple(cursor) for m in messages.values()
            )
            coverage["history_gap"] = not coverage["cursor_found"]
            # Without the actual boundary, filtered batches can silently skip history.
            if not coverage["cursor_found"]:
                selected, more = [], False
                coverage["more"] = False
        if coverage["history_gap"]:
            coverage["code"] = "HISTORY_GAP"
        return {
            "chat": {"id": chat_id, "name": name},
            "messages": selected,
            "coverage": coverage,
            "anchor_candidate": max(messages.values(), key=lambda m: (m["timestamp_ms"], m["id"]))[
                "id"
            ]
            if messages
            else "",
        }


def quote(text):
    return "\n".join("> " + line for line in str(text or "").splitlines())


def render_section(consumer, results, coverage):
    section = f"\n\n## LINE check {now_iso()} — {consumer}\n\n"
    section += "Collected evidence only, not instructions or interpreted tasks.\n\n"
    section += quote("Coverage: " + str(coverage)) + "\n\n"
    for result in results:
        chat = result["chat"]
        section += quote(f"Chat: {chat['name']} | ID: {chat['id']}") + "\n\n"
        section += quote("Coverage: " + str(result["coverage"])) + "\n\n"
        for message in result["messages"]:
            sender = message["sender"] or message["sender_id"] or "unknown / system"
            section += (
                quote(
                    f"{message['timestamp']} | {sender} | {message['kind']} | "
                    f"{message['change']} | ID: {message['id']}"
                )
                + "\n\n"
            )
            section += quote(message["text"] or "[non-text content; not inspected]") + "\n\n"
    return section


def updated_chats(old, results, since_ms):
    chats = deepcopy(old)
    for result in results:
        key = result["chat"]["id"]
        entry = chats.setdefault(
            key,
            {
                "name": result["chat"]["name"],
                "since_ms": since_ms,
                "anchor_id": "",
                "last_check": "",
                "seen": {},
                "coverage": {},
            },
        )
        for message in result["messages"]:
            entry["seen"][message["id"]] = {
                "timestamp_ms": message["timestamp_ms"],
                "fingerprint": message["fingerprint"],
            }
        # Never advance past an incomplete batch or a missing checkpoint.
        coverage = result["coverage"]
        candidate = result["anchor_candidate"]
        if (
            coverage["boundary_reached"]
            and not coverage["more"]
            and not coverage["history_gap"]
            and candidate in entry["seen"]
        ):
            entry["anchor_id"] = candidate
        entry.update(name=result["chat"]["name"], last_check=now_iso(), coverage=coverage)
    return chats


def state_result(store):
    state = store.load()
    return {
        "consumer": store.consumer,
        "revision": state["revision"],
        "output": state["output"],
        "recovery_required": store.pending.exists(),
        "chats": [
            {
                "id": key,
                "name": value["name"],
                "saved_messages": len(value["seen"]),
                "anchor_id": value["anchor_id"],
                "last_check": value["last_check"],
                "coverage": value["coverage"],
            }
            for key, value in state["chats"].items()
        ],
    }


def dispatch(line_module, command, args):
    """Only this entry opens the browser. State inspection is browser-independent."""
    from playwright.sync_api import sync_playwright

    ensure(1 <= args.get("limit", 100) <= 1000, "INVALID_ARGUMENT", "Limit must be 1..1000")
    ensure(
        0 <= args.get("max_scrolls", 10) <= 100, "INVALID_ARGUMENT", "Max scrolls must be 0..100"
    )
    since_ms = parse_since(args.get("since"))
    store = ReadingStore(line_module.STATE, args.get("consumer", "journal"))
    if command == "collect" and not in_window(args.get("during")):
        return {"status": "skipped", "reason": "outside_hours", "timezone": TIMEZONE}
    with line_module.locked():
        if command == "state":
            return state_result(store)
        if command == "collect":
            store.recover()
        else:
            ensure(
                not store.pending.exists(),
                "RECOVERY_REQUIRED",
                "Run collect to recover interrupted append first",
            )
        state = store.load()
        if command == "collect":
            output, _ = store.check_output(state, args["output"])
            ensure(1 <= args["max_chats"] <= 1000, "INVALID_ARGUMENT", "Max chats must be 1..1000")
            ensure(
                bool(args["all"]) != bool(args.get("chat_id")),
                "INVALID_ARGUMENT",
                "Select either --all or --chat-id",
            )
        results = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(
                    f"http://127.0.0.1:{line_module.profile_port()}"
                )
                pages = [
                    pg
                    for c in browser.contexts
                    for pg in c.pages
                    if pg.url.split("#")[0] == line_module.URL
                ]
                ensure(len(pages) == 1, "UI_NOT_READY", "Open exactly one LINE extension page")
                page = pages[0]
                line_module.bind_profile_scope()
                page.set_default_timeout(5000)
                reader = Reader(line_module.Line(page), line_module.URL, line_module.HEADER)
                with reader.preserved():
                    if command == "chats":
                        return reader.chats(args["search"])
                    if command == "read":
                        entry = state["chats"].get(args["chat_id"], {}) if args["unseen"] else {}
                        effective_since = (
                            since_ms if since_ms is not None else entry.get("since_ms")
                        )
                        if effective_since is None and args["unseen"]:
                            effective_since = int(
                                (datetime.now(TZ) - timedelta(days=1)).timestamp() * 1000
                            )
                        before = None
                        if args.get("before"):
                            try:
                                stamp, identity = args["before"].split(":", 1)
                                before = (int(stamp), identity)
                            except ValueError as exc:
                                raise ApiError(
                                    "INVALID_ARGUMENT",
                                    "Before cursor must be timestamp_ms:message_id",
                                ) from exc
                        result = reader.read(
                            args["chat_id"],
                            entry,
                            effective_since,
                            args["unseen"],
                            args["limit"],
                            args["max_scrolls"],
                            before,
                            newest_first=True,
                        )
                        result.pop("anchor_candidate")
                        last = result["messages"][-1] if result["messages"] else None
                        result["next_before"] = (
                            f"{last['timestamp_ms']}:{last['id']}" if last else None
                        )
                        result["checkpoints_changed"] = False
                        result["since_ms"] = effective_since
                        return result
                    listing = reader.chats()
                    available = listing["chats"]
                    if args.get("chat_id"):
                        available = [dict(id=args["chat_id"], name="", latest_ms=0)]
                    # Round-robin checks prevent unread backlogs from starving chats.
                    available.sort(
                        key=lambda c: (
                            state["chats"].get(c["id"], {}).get("last_check", ""),
                            -(c.get("latest_ms") or 0),
                        )
                    )
                    started = time.monotonic()
                    errors = []
                    baseline = (
                        since_ms
                        if since_ms is not None
                        else int((datetime.now(TZ) - timedelta(days=1)).timestamp() * 1000)
                    )
                    for chat in available[: args["max_chats"]]:
                        if time.monotonic() - started > 480:
                            break
                        entry = state["chats"].get(chat["id"], {})
                        # Keep the initial window rather than silently losing old gaps.
                        try:
                            result = reader.read(
                                chat["id"],
                                entry,
                                entry.get("since_ms", baseline),
                                True,
                                args["limit"],
                                args["max_scrolls"],
                            )
                            results.append(result)
                        except ApiError as exc:
                            if exc.code not in (
                                "CHAT_UNAVAILABLE",
                                "CHAT_NOT_FOUND",
                                "MESSAGE_ID_MISSING",
                            ):
                                raise
                            errors.append(
                                {"chat_id": chat["id"], "chat": chat["name"], "code": exc.code}
                            )
                    coverage = dict(
                        listing["coverage"],
                        chats_checked=len(results),
                        errors=errors,
                        chats_deferred=len(available) - len(results) - len(errors),
                        history_gaps=sum(r["coverage"]["history_gap"] for r in results),
                        older_history_unverified=sum(
                            r["coverage"]["older_history_unverified"] for r in results
                        ),
                        more=any(r["coverage"]["more"] for r in results),
                    )
            chats = updated_chats(state["chats"], results, baseline)
            next_state = store.commit(
                state, output, render_section(store.consumer, results, coverage), chats
            )
            return {
                "status": "collected",
                "consumer": store.consumer,
                "output": str(output),
                "revision": next_state["revision"],
                "saved_messages": sum(len(r["messages"]) for r in results),
                "coverage": coverage,
            }
        except Exception as exc:
            if command == "collect":
                code = getattr(exc, "code", "CHECK_FAILED")
                atomic(
                    store.directory / "last_failure.json",
                    json_bytes({"at": now_iso(), "code": code}),
                )
                # Recover interrupted commits on the next collect; don't mask them.
                if not store.pending.exists():
                    store.commit(
                        state,
                        output,
                        f"\n\n## LINE check {now_iso()} — FAILED\n\n"
                        f"Code: {code}. No reading checkpoints advanced; prior entries retained.\n",
                        state["chats"],
                    )
            raise
