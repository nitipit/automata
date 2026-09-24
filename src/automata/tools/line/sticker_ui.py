"""Observed LINE Chrome sticker DOM adapter; never click tiles for inspection.

Stable identity joins package asset ID, data-sticker-key, data-product-id and
sticker asset ID. Only the observed bare UUID cache-buster is ignored. Unknown
assets, effect stickers and ambiguous/pre-existing picker windows fail closed.
"""

import re
from urllib.parse import urlsplit

from sticker_api import StickerError, StickerOperations, fingerprint, require

ORIGIN = "chrome-extension://ophjlpahpchlmihnnnihgmmeilfjmjjc/"
INDEX = ORIGIN + "index.html"
POPUP = ORIGIN + "popup.html"
CDN = "https://stickershop.line-scdn.net"
UUID_QUERY = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
ASSET = re.compile(r"/stickershop/v1/sticker/([0-9]+)/android/sticker\.png")
PACKAGE = re.compile(r"/stickershop/v1/product/([0-9]+)/android/tab_on\.png")
ROOM = '[class*="chatroom-module__chatroom__"]'


def numeric(value):
    require(
        isinstance(value, str) and re.fullmatch(r"[0-9]+", value),
        "INVALID_ARGUMENT",
        "Package/sticker IDs must be verified numeric IDs",
    )
    return value


def asset_identity(src):
    url = urlsplit(src)
    match = ASSET.fullmatch(url.path)
    require(
        url.scheme == "https"
        and url.netloc == "stickershop.line-scdn.net"
        and not url.fragment
        and match is not None
        and (not url.query or UUID_QUERY.fullmatch(url.query)),
        "STICKER_UI_UNVERIFIED",
        "Unsupported sticker asset URL; do not guess its identity",
    )
    return match[1], CDN + url.path


class Picker:
    def __init__(self, line, chat_id, popup):
        self.line, self.chat_id, self.popup = line, chat_id, popup
        self.route = line.page.url
        self.clicked = False

    def guard(self):
        self.line.verify(self.chat_id)
        require(
            self.line.page.url == self.route
            and not self.popup.is_closed()
            and self.popup.url == POPUP
            and self.popup.opener() == self.line.page,
            "STICKER_CONTEXT_CHANGED",
            "Sticker picker or recipient binding changed",
        )
        context = self.line.page.context
        require(
            [p for p in context.pages if p.url.split("#", 1)[0] == INDEX] == [self.line.page]
            and [p for p in context.pages if p.url.split("#", 1)[0].split("?", 1)[0] == POPUP]
            == [self.popup],
            "STICKER_PICKER_AMBIGUOUS",
            "Multiple LINE main pages or sticker pickers",
        )

    def packages(self):
        self.guard()
        rows = self.popup.get_by_role("tab", name="sticker package", exact=True).evaluate_all(
            """es=>es.slice(0,100).map(e=>({images:e.querySelectorAll('img').length,
            src:e.querySelector('img')?.src,name:e.querySelector('img')?.alt}))"""
        )
        result = []
        for row in rows:
            url = urlsplit(row.get("src") or "")
            match = PACKAGE.fullmatch(url.path)
            require(
                row["images"] == 1
                and url.scheme == "https"
                and url.netloc == "stickershop.line-scdn.net"
                and not url.query
                and not url.fragment
                and match is not None,
                "STICKER_UI_UNVERIFIED",
                "Unrecognized package tab identity",
            )
            result.append({"package_id": match[1], "name": row["name"], "preview_url": row["src"]})
        require(
            len({r["package_id"] for r in result}) == len(result),
            "STICKER_AMBIGUOUS",
            "Duplicate package identities",
        )
        return result

    def select(self, package_id):
        self.guard()
        numeric(package_id)
        tab = self.popup.get_by_role("tab", name="sticker package", exact=True).filter(
            has=self.popup.locator(
                f'img[src="{CDN}/stickershop/v1/product/{package_id}/android/tab_on.png"]'
            )
        )
        require(tab.count() == 1, "STICKER_PACKAGE_MISSING", "Package not uniquely available")
        if tab.get_attribute("aria-selected") != "true":
            tab.click()  # Package navigation only; NEVER a sticker tile.
        self.popup.locator(
            f'[role="tab"][aria-selected="true"]:has(img[src="{CDN}/stickershop/v1/product/{package_id}/android/tab_on.png"])'
        ).wait_for()
        self.popup.locator(f'[data-sticker-key^="{package_id}/"]').first.wait_for()
        self.guard()

    def tile(self, tile):
        require(tile.count() == 1, "STICKER_AMBIGUOUS", "Sticker missing or ambiguous")
        row = tile.evaluate("""e=>({key:e.dataset.stickerKey,
            images:e.querySelectorAll('img').length,
            src:e.querySelector('img')?.src,product:e.querySelector('img')?.dataset.productId,
            owned:e.querySelector('img')?.dataset.isOwned,
            effect:e.querySelector('img')?.dataset.isEffectSticker})""")
        key = re.fullmatch(r"([0-9]+)/([0-9]+)", row.get("key") or "")
        require(
            key is not None
            and row["images"] == 1
            and row["owned"] == "true"
            and row["effect"] == "false"
            and row["product"] == key[1],
            "STICKER_UI_UNVERIFIED",
            "Unsupported, unowned, effect, or inconsistent sticker tile",
        )
        sticker_id, canonical = asset_identity(row["src"])
        require(
            sticker_id == key[2], "STICKER_IDENTITY_CHANGED", "Tile and asset identity disagree"
        )
        return {"package_id": key[1], "sticker_id": sticker_id, "preview_url": canonical}

    def catalog(self, package_id, limit):
        packages = self.packages()
        items, observed = [], 0
        if package_id is not None:
            self.select(package_id)
            tiles = self.popup.locator(f'[data-sticker-key^="{package_id}/"]')
            observed = tiles.count()
            for index in range(min(observed, limit)):
                tile = tiles.nth(index)
                # Position enumerates DOM only; identity always comes from attributes.
                try:
                    items.append({**self.tile(tile), "supported": True})
                except StickerError as exc:
                    items.append({"supported": False, "code": exc.code})
        return {
            "packages": packages,
            "stickers": items,
            "coverage": {
                "complete": False,
                "scope": "loaded DOM only; no scrolling",
                "observed_stickers": observed,
                "returned_stickers": len(items),
            },
        }

    def find(self, package_id, sticker_id):
        numeric(package_id)
        numeric(sticker_id)
        self.select(package_id)
        return self.tile(self.popup.locator(f'[data-sticker-key="{package_id}/{sticker_id}"]'))

    def outgoing_ids(self):
        self.guard()
        rows = self.line.room.locator('[data-message-select-id][data-direction="reverse"]')
        require(rows.count() <= 1000, "STICKER_HISTORY_BOUND", "Too many loaded outgoing rows")
        return rows.evaluate_all("es=>es.map(e=>e.dataset.messageSelectId)")

    def click_once(self, selected):
        self.guard()
        require(not self.clicked, "STICKER_ALREADY_ATTEMPTED", "Never repeat a sticker click")
        package_id, sticker_id = numeric(selected["package_id"]), numeric(selected["sticker_id"])
        tile = self.popup.locator(f'[data-sticker-key="{package_id}/{sticker_id}"]')
        require(
            fingerprint(self.tile(tile)) == fingerprint(selected),
            "STICKER_IDENTITY_CHANGED",
            "Sticker changed immediately before dispatch",
        )
        self.clicked = True
        tile.click()

    def wait_outgoing(self, selected, baseline):
        # No transcript text is collected. Observe only newly rendered metadata.
        result = self.line.page.wait_for_function(
            """s=>{
              const rooms=document.querySelectorAll(s.room);
              if(location.href!==s.route||rooms.length!==1||rooms[0].dataset.mid!==s.chat)
                return {error:'recipient changed'};
              const found=[];
              const selector='[data-message-select-id][data-direction="reverse"]';
              for(const e of rooms[0].querySelectorAll(selector)) {
                const id=e.dataset.messageSelectId;
                if(!id||s.baseline.includes(id))continue;
                for(const img of e.querySelectorAll('img[data-product-id]')) {
                  if(img.dataset.productId!==s.product)continue;
                  const u=new URL(img.src);
                  if(u.username||u.password||u.hash||
                     (u.search&&!new RegExp(s.cacheQuery).test(u.search.slice(1))))continue;
                  if(u.origin+u.pathname!==s.asset)continue;
                  found.push({message_id:id,chat_id:s.chat,direction:'outgoing',
                              package_id:s.product,sticker_id:s.sticker});
                }
              }
              if(found.length>1)return {error:'ambiguous new outgoing stickers'};
              return found.length===1?found[0]:false;
            }""",
            arg={
                "room": ROOM,
                "route": self.route,
                "chat": self.chat_id,
                "product": selected["package_id"],
                "sticker": selected["sticker_id"],
                "asset": selected["preview_url"],
                "baseline": list(baseline),
                "cacheQuery": "^" + UUID_QUERY.pattern + "$",
            },
            timeout=5000,
        ).json_value()
        require(
            "error" not in result,
            "STICKER_EVIDENCE_MISSING",
            "Ambiguous or changed recipient evidence",
        )
        return result

    def close(self):
        # Handle identity, not a broad popup selector; a navigated recipient cannot
        # cause us to close another window. Closing is never send rollback.
        if not self.popup.is_closed():
            self.popup.close()


def open_picker(line, chat_id):
    line.verify(chat_id)
    main = line.page
    require(
        main.url.startswith(INDEX + "#/chats/"), "STICKER_UI_UNVERIFIED", "Unexpected LINE route"
    )
    context = main.context
    require(
        [p for p in context.pages if p.url.split("#", 1)[0] == INDEX] == [main]
        and not any(p.url.split("#", 1)[0].split("?", 1)[0] == POPUP for p in context.pages),
        "STICKER_PICKER_AMBIGUOUS",
        "Close existing picker manually; exactly one LINE main page is required",
    )
    before = set(context.pages)
    popup = None
    owned = False
    try:
        with context.expect_page(
            predicate=lambda page: page.opener() == main, timeout=5000
        ) as event:
            main.get_by_role("button", name="Select sticker", exact=True).click()
        popup = event.value
        require(popup not in before, "STICKER_PICKER_AMBIGUOUS", "Picker was not newly opened")
        owned = True  # A new page with this exact opener was observed by our event predicate.
        popup.set_default_timeout(5000)
        popup.wait_for_load_state("domcontentloaded")
        require(popup.url == POPUP, "STICKER_UI_UNVERIFIED", "Unexpected picker URL")
        popup.get_by_role("tab", name="sticker package", exact=True).first.wait_for()
        picker = Picker(line, chat_id, popup)
        picker.guard()
        return picker
    except Exception as exc:
        cleanup = StickerOperations.close(popup if owned else None)
        raise StickerError(
            getattr(exc, "code", "STICKER_PICKER_FAILED"), str(exc), cleanup=cleanup
        ) from exc
