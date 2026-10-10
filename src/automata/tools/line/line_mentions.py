"""Native mentions: keyboard selection and public composer identity evidence only."""

from dictify import Model
from line_contracts import MentionIdentity
from line_runtime import require


def validated_identity(value):
    try:
        return MentionIdentity(value).dict()
    except (ValueError, TypeError, Model.Error) as exc:
        raise RuntimeError("Malformed mention identity; stopped") from exc


def composer_mentions(editor, required=False):
    """Read TEXTAREA-EX's public value getter; never inspect framework/app state."""
    value = editor.evaluate("""el => {
      const host = el.getRootNode().host;
      return host ? {available: true, value: host.value} : {available: false};
    }""")
    if not value["available"]:
        require(not required, "Public composer mention identity unavailable; stopped")
        return []
    parts = value.get("value")
    require(isinstance(parts, list), "Malformed public composer value; stopped")
    mentions = []
    for part in parts:
        if isinstance(part, str):
            continue
        require(
            isinstance(part, dict) and part.get("type") == "mention",
            "Unsupported or malformed composer metadata; stopped",
        )
        label = part.get("altText")
        extra = part.get("extra")
        data = extra.get("data") if isinstance(extra, dict) else None
        require(
            isinstance(label, str) and label.startswith("@") and isinstance(data, dict),
            "Mention identity missing; stopped",
        )
        if set(data) == {"M"}:
            identity = {"kind": "individual", "name": label[1:], "member_id": data["M"]}
        elif data == {"A": "1"}:
            identity = {"kind": "all", "name": label[1:], "member_id": None}
        else:
            raise RuntimeError("Malformed or mixed individual/All identity; stopped")
        mentions.append(validated_identity(identity))
    require(len(mentions) <= 1, "Multiple native mentions are unsupported; stopped")
    return mentions


def verify_mention(editor, expected):
    mentions = composer_mentions(editor, required=True)
    require(mentions == [expected], "Composer mention identity mismatch; nothing sent")
    return mentions[0]


def prepare_mention(line, chat_id, member, text, chat=None, member_id=None, mention_all=False):
    require(
        (mention_all and member is None and member_id is None)
        or (not mention_all and isinstance(member, str) and member.strip() and member != "All"),
        "Choose an individual or explicit All mention; no fallback",
    )
    line.empty(chat_id, chat)
    editor = line.room.locator("textarea")
    editor.fill("@")
    editor.focus()
    name = "All" if mention_all else member
    # The picker can remember a previous active individual, even for a new @.
    # Query All explicitly too; never assume the default active option is All.
    line.page.keyboard.insert_text(name)
    options = line.page.get_by_role("option")
    options.first.wait_for()
    matches = options.filter(has=line.page.get_by_text(name, exact=True))
    matches.first.wait_for()
    if member_id is not None:
        # Resolve IDs without interpolating user data into a selector.
        candidates = [matches.nth(i) for i in range(matches.count())]
        candidates = [
            o
            for o in candidates
            if o.locator("button[data-id]").count() == 1
            and o.locator("button[data-id]").get_attribute("data-id") == member_id
        ]
        require(len(candidates) == 1, "Member ID missing or ambiguous; nothing sent")
        selected = candidates[0]
    else:
        require(matches.count() == 1, "Member missing or ambiguous; nothing sent")
        selected = matches.first
    button = selected.locator("button[data-id]")
    require(button.count() == 1, "Mention option identity missing; stopped")
    resolved_id = button.get_attribute("data-id")
    expected = validated_identity(
        {
            "kind": "all" if mention_all else "individual",
            "name": name,
            "member_id": None if mention_all else resolved_id,
        }
    )
    require(not mention_all or resolved_id == "", "All option has an individual ID; stopped")
    from playwright.sync_api import expect

    expect(selected).to_have_attribute("aria-selected", "true")
    line.verify(chat_id, chat)
    require(
        selected.get_attribute("aria-selected") == "true"
        and button.get_attribute("data-id") == resolved_id,
        "Active mention option changed; stopped",
    )
    # Click can insert the still-active All option despite a named button target.
    editor.press("Enter")
    expect(options).to_have_count(0)
    verify_mention(editor, expected)
    marker = line.room.locator('[part~="mention"]')
    require(marker.count() == 1, "Native mention marker missing; stopped")
    before = editor.input_value()
    if text:
        require(
            len((before + text).encode("utf-16-le")) // 2 <= 10000,
            "Mention plus text is too long",
        )
        editor.press("Control+End")
        editor.focus()
        line.page.keyboard.insert_text(text)
    require(editor.input_value() == before + text, "Mention suffix changed unexpectedly")
    verify_mention(editor, expected)
    return line.prepare(chat_id, expected)
