"""Opt-in real Web Chat/Pi/Chrome check, using only isolated offline fixtures.

After npm run build:web, run with the web extra and Playwright installed:
    python tests/integration/automata/tools/web_sessions_picker.py
Uses the installed Pi and Chrome; neither a user profile nor a model service.
"""

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from playwright.async_api import async_playwright, expect

from automata.tools.web.host import BrowserHost


async def start_host(directory, store):
    fixture = Path(__file__).with_suffix(".ts").resolve()
    host = BrowserHost()
    await host.start(
        cwd=directory,
        provider="picker-fixture",
        model="fixture",
        extra_args=(
            "--offline",
            "--no-extensions",
            "--no-skills",
            "--no-prompt-templates",
            "--no-themes",
            "--session-dir",
            str(store),
            "-e",
            str(fixture),
        ),
    )
    return host


async def seed(host, label, message):
    chat = host.initial_session
    await chat.handle_command({"type": "rename", "id": "name", "name": label})
    assert chat.state["sessionName"] == label
    await chat.handle_command({"type": "prompt", "id": "seed", "message": message})
    async with asyncio.timeout(10):
        while chat.state["status"] == "running":
            await asyncio.sleep(0.01)
    assert chat.state["status"] == "idle", chat.state["status"]
    assert chat.messages[-1]["content"][0]["text"] == f"Offline history: {message}"


async def choose(page, label):
    await page.get_by_role("button", name="Sessions", exact=True).click()
    picker = page.get_by_role("dialog", name="Project sessions")
    await expect(picker).to_be_visible()
    await picker.get_by_role("button", name=label, exact=False).click()
    await expect(picker.get_by_role("button", name="Other project", exact=False)).to_have_count(0)
    assert await picker.evaluate("node => node.scrollWidth <= node.clientWidth + 1")
    return picker


async def open_selected(picker):
    opening = picker.get_by_role("button", name="Open session")
    await expect(picker.get_by_role("checkbox")).to_have_count(0)
    await expect(picker.locator("#sessions-caution")).to_contain_text("close this session")
    await expect(picker.locator("#sessions-caution")).to_be_visible()
    await expect(opening).to_be_enabled()
    await opening.click()


async def check_page(host_a, host_b, browser):
    page = await browser.new_page(viewport={"width": 390, "height": 844})
    errors = []
    page.on("pageerror", lambda _error: errors.append(True))
    a, b = host_a.initial_session, host_b.initial_session
    a_id, b_id = a.id, b.id
    await page.goto(host_a.admission_url)

    async def current_is(expected):
        assert await page.evaluate("location.pathname") == f"/sessions/{expected}/"
        assert len(page.context.pages) == 1 and a.id == a_id and b.id == b_id
    sessions = page.get_by_role("button", name="Sessions", exact=True)
    title = page.locator("#session-name")
    transcript = page.locator("#transcript")
    prompt = page.locator("#prompt")
    send = page.get_by_role("button", name="Send message", exact=True)
    await expect(title).to_have_text("Conversation A")
    await expect(sessions).to_be_enabled()
    await expect(transcript).to_contain_text("Offline history: A first")

    # Busy disables the picker. Previewing another row does not switch.
    await prompt.fill("A continues")
    await send.click()
    await expect(sessions).to_be_disabled()
    await expect(transcript).to_contain_text("Offline history: A first | A continues")
    await expect(sessions).to_be_enabled()
    await prompt.fill("Unsent draft for A")
    picker = await choose(page, "Conversation B")
    await expect(picker.get_by_role("heading", name="Conversation B")).to_be_focused()
    await expect(picker.locator("#sessions-user")).to_have_text("B first")
    await expect(picker.locator("#sessions-assistant")).to_have_text("Offline history: B first")
    await expect(picker.locator("#sessions-model")).to_have_text("picker-fixture/fixture")
    await expect(picker.locator("#sessions-tokens")).to_have_text("2")
    await expect(picker.get_by_text("Saved context window", exact=True)).to_have_count(0)
    await current_is(a_id)
    await picker.get_by_role("button", name="Back to sessions", exact=False).click()
    await expect(picker.get_by_role("button", name="Conversation B", exact=False)).to_be_focused()
    current = picker.get_by_role("button", name="Conversation A", exact=False)
    await expect(current).to_have_attribute("aria-current", "true")
    await current.press("Enter")
    await expect(picker.get_by_text("CURRENT SESSION", exact=True)).to_be_visible()
    await expect(picker.get_by_role("button", name="Open session")).to_have_count(0)
    await page.keyboard.press("Escape")
    await expect(picker).not_to_be_visible()
    await expect(sessions).to_be_focused()
    await expect(prompt).to_have_value("Unsent draft for A")

    # An explicit Open cannot override another Web Chat host's lock.
    picker = await choose(page, "Conversation B")
    await open_selected(picker)
    await expect(picker.locator("#sessions-status")).to_contain_text(
        "could not be claimed"
    )
    await current_is(a_id)
    await expect(prompt).to_have_value("Unsent draft for A")
    await host_b.close()
    await picker.get_by_role("button", name="Reload list").click()
    await picker.get_by_role("button", name="Conversation B", exact=False).click()
    await open_selected(picker)
    await expect(picker).not_to_be_visible()
    await expect(title).to_have_text("Conversation B")
    await current_is(b_id)
    await expect(transcript).to_contain_text("Offline history: B first")
    await expect(transcript).not_to_contain_text("A first")
    await expect(prompt).to_have_value("")
    await prompt.fill("B continues")
    await send.click()
    await expect(transcript).to_contain_text("Offline history: B first | B continues")
    await expect(sessions).to_be_enabled()

    picker = await choose(page, "Conversation A")
    await expect(picker.get_by_role("heading", name="Conversation A")).to_be_visible()
    await open_selected(picker)
    await expect(title).to_have_text("Conversation A")
    await expect(transcript).to_contain_text("Offline history: A first | A continues")
    await expect(transcript).not_to_contain_text("B continues")
    await expect(prompt).to_have_value("Unsent draft for A")
    await current_is(a_id)

    # Open B again and check its native persisted history.
    picker = await choose(page, "Conversation B")
    await open_selected(picker)
    await expect(title).to_have_text("Conversation B")
    await expect(transcript).to_contain_text("Offline history: B first | B continues")
    await expect(transcript).not_to_contain_text("A continues")
    await expect(prompt).to_have_value("")
    await current_is(b_id)
    await page.reload()
    await expect(sessions).to_be_enabled()
    await expect(title).to_have_text("Conversation B")
    await expect(transcript).to_contain_text("Offline history: B first | B continues")
    assert not errors, "Unexpected browser JavaScript error"
    await page.close()


async def main():
    with tempfile.TemporaryDirectory(prefix="automata-session-picker-") as temp:
        root = Path(temp)
        home, agent, project, other, store = (
            root / name for name in ("home", "agent", "project", "other", "store")
        )
        for directory in (home, agent, project, other, store):
            directory.mkdir()
        with patch.dict(os.environ, {"HOME": str(home), "PI_CODING_AGENT_DIR": str(agent)}):
            os.environ.pop("PI_SESSION_FILE", None)
            foreign = await start_host(other, store)
            try:
                await seed(foreign, "Other project", "Foreign first")
            finally:
                await foreign.close()
            host_b = await start_host(project, store)
            try:
                await seed(host_b, "Conversation B", "B first")
                host_a = await start_host(project, store)
                try:
                    await seed(host_a, "Conversation A", "A first")
                    chrome = shutil.which("google-chrome") or shutil.which("chromium")
                    assert chrome, "Chrome or Chromium is required"
                    async with async_playwright() as playwright:
                        browser = await playwright.chromium.launch(executable_path=chrome)
                        try:
                            await check_page(host_a, host_b, browser)
                        finally:
                            await browser.close()
                finally:
                    await host_a.close()
            finally:
                await host_b.close()
    print(
        "Native Pi A/B history, offline model context, busy/active guards, browser and reload: pass"
    )


if __name__ == "__main__":
    asyncio.run(main())
