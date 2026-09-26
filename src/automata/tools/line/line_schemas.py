"""Validated agent-facing command inputs; no browser or state access."""

import inspect
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Annotated, get_type_hints
from zoneinfo import ZoneInfo

from cyclopts import Parameter
from dictify import Field, Model


def date_ms(value):
    if value is None:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError("Timestamps require an explicit timezone offset")
            result = result.replace(
                tzinfo=ZoneInfo(os.environ.get("AUTOMATA_LINE_TIMEZONE", "UTC"))
            )
        return int(result.timestamp() * 1000)
    except (ValueError, KeyError) as exc:
        raise ValueError("Use ISO dates or timezone-qualified timestamps") from exc


def cursor_key(value):
    if value is None:
        return None
    parts = value.split(":", 1)
    if len(parts) != 2 or not parts[0].isdigit() or int(parts[0]) <= 0 or not parts[1]:
        raise ValueError("Cursor must be timestamp_ms:message_id from a read result")
    return int(parts[0]), parts[1]


ChatId = Annotated[
    str,
    Field(required=True).match(r"[A-Za-z0-9_-]+$"),
    Parameter(help="Stable chat ID returned by chats."),
]
Limit = Annotated[
    int,
    Field(default=50).verify(lambda n: 1 <= n <= 1000),
    Parameter(help="Maximum messages returned, 1..1000."),
]


def cli_model(cls):
    """Preserve CLI metadata stripped from Dictify's otherwise useful signature."""
    signature = inspect.signature(cls)
    hints = get_type_hints(cls, include_extras=True)
    cls.__signature__ = signature.replace(
        parameters=[
            p.replace(annotation=hints.get(p.name, p.annotation))
            for p in signature.parameters.values()
        ]
    )
    cls.__init__.__signature__ = cls.__signature__
    return cls


@cli_model
class Chat(Model):
    chat_id: ChatId


@cli_model
class Chats(Model):
    search: Annotated[str, Field(default=""), Parameter(help="Case-insensitive name substring.")]


@cli_model
class Read(Chat):
    limit: Limit
    since: Annotated[str | None, Field(default=None), Parameter(help="Inclusive ISO date/time.")]
    until: Annotated[str | None, Field(default=None), Parameter(help="Exclusive ISO date/time.")]
    before: Annotated[
        str | None, Field(default=None), Parameter(help="Exclusive older-history cursor.")
    ]
    after: Annotated[
        str | None,
        Field(default=None),
        Parameter(help="Exclusive newer-history cursor; oldest-first."),
    ]
    max_scrolls: Annotated[
        int,
        Field(default=10).verify(lambda n: 0 <= n <= 100),
        Parameter(help="Bound older-history loading attempts, 0..100."),
    ]

    def post_validate(self):
        if self.before and self.after:
            raise ValueError("Choose --before OR --after")
        cursor_key(self.before)
        cursor_key(self.after)
        begin, end = date_ms(self.since), date_ms(self.until)
        if begin is not None and end is not None and begin >= end:
            raise ValueError("--since must precede --until")


@cli_model
class Stickers(Chat):
    package_id: Annotated[
        str | None, Field(default=None), Parameter(help="Exact package ID filter.")
    ]
    limit: Annotated[int, Field(default=100).verify(lambda n: 1 <= n <= 100)]


@cli_model
class Send(Chat):
    text: Annotated[
        str | None, Field(default=None), Parameter(help="Exact text; @Name is plain text.")
    ]
    mention: Annotated[
        str | None, Field(default=None), Parameter(help="Exact individual native-mention name.")
    ]
    image: Annotated[Path | None, Field(default=None), Parameter(help="One local PNG file.")]
    sticker_package: Annotated[
        str | None, Field(default=None), Parameter(help="Verified sticker package ID.")
    ]
    sticker_id: Annotated[str | None, Field(default=None), Parameter(help="Verified sticker ID.")]
    draft: Annotated[
        bool, Field(default=False), Parameter(help="Prepare only; return a confirmation token.")
    ]
    confirm: Annotated[
        str | None, Field(default=None), Parameter(help="Send the exact prepared content once.")
    ]

    def post_validate(self):
        if self.confirm is not None:
            if (
                not self.confirm
                or self.draft
                or any(
                    x is not None
                    for x in (
                        self.text,
                        self.mention,
                        self.image,
                        self.sticker_package,
                        self.sticker_id,
                    )
                )
            ):
                raise ValueError("--confirm requires a token and excludes content options/--draft")
            return
        modes = (
            self.text is not None or self.mention is not None,
            self.image is not None,
            self.sticker_package is not None or self.sticker_id is not None,
        )
        if sum(modes) != 1:
            raise ValueError("Choose text/mention, image, or sticker content")
        if modes[0]:
            if self.mention is not None and (not self.mention.strip() or self.mention == "All"):
                raise ValueError("Mention requires a named individual, not All")
            if not self.text and not self.mention:
                raise ValueError("Text must be nonempty")
            if self.text and len(self.text.encode("utf-16-le")) // 2 > 10000:
                raise ValueError("Text exceeds 10000 UTF-16 units")
        if modes[1]:
            if not self.image.is_file():
                raise ValueError("--image must be an existing PNG")
            with self.image.open("rb") as image:
                if image.read(8) != b"\x89PNG\r\n\x1a\n":
                    raise ValueError("--image must be an existing PNG")
        if modes[2] and not (self.sticker_package and self.sticker_id):
            raise ValueError("Sticker requires both --sticker-package and --sticker-id")
