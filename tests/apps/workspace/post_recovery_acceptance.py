"""Lost HTTP save receipt recovery in the isolated mock-delivery browser harness."""
from playwright.sync_api import expect


def verify_uncertain_save(context, url, control, project_root):
    page = context.new_page()
    page.goto(f"{url}{project_root}", wait_until="networkidle")

    def lose_saved_receipt(route):
        # Backend committed, but caller never learns the HTTP outcome.
        response = route.fetch(headers={**route.request.headers, "sec-fetch-site": "same-origin"})
        assert response.status == 200, response.text()
        route.abort()

    page.route("**/api/conversation-posts", lose_saved_receipt)
    control(page, "wsp-composer textarea").fill("Save receipt lost, never replay")
    expect(control(page, ".notice")).to_contain_text("All changes saved")
    control(page, "wsp-composer #send").click()
    expect(control(page, ".notice")).to_contain_text("no automatic replay")
    held = page.evaluate("""Object.keys(localStorage)
        .filter(k => k.startsWith('workspace-pending-post-v1:'))
        .map(k => JSON.parse(localStorage[k]))""")
    assert len(held) == 1
    operation = held[0]["operationId"]
    assert page.evaluate("mockRouter.requests.length") == 0
    page.close()
    recovered = context.new_page()
    recovered.goto(f"{url}{project_root}", wait_until="networkidle")
    expect(control(recovered, ".notice")).to_contain_text("Previous input is saved")
    assert recovered.evaluate("mockRouter.requests.length") == 0
    assert recovered.evaluate("""Object.keys(localStorage)
        .filter(k => k.startsWith('workspace-pending-post-v1:')).length""") == 0
    messages = recovered.request.get(f"{url}/api/state").json()[
        "conversations"]["conversation-aster"]["messages"]
    assert len([m for m in messages if m["operationId"] == operation]) == 1
    recovered.close()
