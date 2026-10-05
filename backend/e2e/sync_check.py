"""End-to-end playback sync check with real YouTube players.

Opens one DJ and several listeners in headless Chromium against the running dev
stack (backend :8000 + Vite :5173), plays a real song, and measures how far each
listener's YouTube player is from the room clock and from each other through
play, pause, seek and skip.

    uv run python e2e/sync_check.py [--listeners 2] [--base http://localhost:5173]

Needs the Vite dev server: it exposes window.__cdj, a debug hook on the player.
"""

import argparse
import asyncio
import json
import secrets
import statistics
import sys
import urllib.request

from playwright.async_api import async_playwright

SONG_QUERY = "Rick Astley Never Gonna Give You Up"
PAUSED, PLAYING = 2, 1


def api(base: str, path: str, body: dict | None = None, token: str | None = None) -> dict:
    req = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})},
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


async def open_person(browser, base: str, room: str, token: str | None, name: str):
    ctx = await browser.new_context()
    await ctx.add_init_script(
        f"sessionStorage.setItem('cdj.token', {json.dumps(token or '')});"
        f"sessionStorage.setItem('cdj.guestName', {json.dumps(name)});"
    )
    page = await ctx.new_page()
    await page.goto(f"{base}/{room}")
    await page.get_by_role("button", name="Tap to listen").click()
    await page.wait_for_function("window.__cdj !== undefined", timeout=20000)
    return page


async def sample(pages) -> list[dict]:
    """Read every player at (nearly) the same instant, normalized to one timestamp."""
    js = """() => { const c = window.__cdj; return {now: performance.timeOrigin + performance.now(),
        t: c.playerTime(), exp: c.expected(), state: c.playerState(), vid: c.videoId(), lead: c.lead()} }"""
    raw = await asyncio.gather(*(p.evaluate(js) for p in pages))
    ref = raw[0]["now"]
    for r in raw:
        shift = (ref - r["now"]) / 1000
        if r["state"] == PLAYING:
            r["t"] += shift
            r["exp"] += shift
        r["drift"] = r["t"] - r["exp"]
    return raw


def report(label: str, rows: list[dict]) -> float:
    spread = max(r["t"] for r in rows) - min(r["t"] for r in rows)
    drifts = ", ".join(f"{r['drift']:+.2f}s" for r in rows)
    states = ",".join(str(r["state"]) for r in rows)
    print(f"  {label:<28} spread={spread:.2f}s  drift vs room clock=[{drifts}]  states=[{states}]")
    return spread


async def main(base: str, listeners: int) -> int:
    failures = []

    def check(ok: bool, what: str):
        print(f"  {'PASS' if ok else 'FAIL'}  {what}")
        if not ok:
            failures.append(what)

    name = f"e2e_{secrets.token_hex(3)}"
    token = api(base, "/api/auth/signup", {"username": name, "password": "e2e-pass-123"})["token"]
    room = api(base, "/api/rooms", {}, token)["pretty_id"]
    print(f"Room {room}: 1 DJ + {listeners} listeners")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required", "--mute-audio"])
        dj = await open_person(browser, base, room, token, "DJ")
        crowd = [await open_person(browser, base, room, None, f"Listener {i + 1}") for i in range(listeners)]
        everyone = [dj, *crowd]

        # Queue two songs from search (so "next" has somewhere to go).
        box = dj.get_by_placeholder("Search songs, or paste a YouTube link")
        await box.fill(SONG_QUERY)
        await dj.locator(".results .add-btn").first.click(timeout=20000)
        await box.fill("Daft Punk One More Time")
        await dj.locator(".results .track", has_text="One More Time").first.locator(".add-btn").click(timeout=20000)
        await box.press("Escape")

        print("\nPlaying")
        await asyncio.sleep(12)  # time to load, start, and learn the startup lead
        spreads = []
        for i in range(5):
            rows = await sample(everyone)
            spreads.append(report(f"sample {i + 1}", rows))
            await asyncio.sleep(2)
        check(all(r["state"] == PLAYING for r in rows), "every player is playing")
        check(len({r["vid"] for r in rows}) == 1, "every player is on the same video")
        check(statistics.median(spreads) < 0.6, f"players within 0.6s of each other (median spread {statistics.median(spreads):.2f}s)")

        print("\nDJ pauses")
        await dj.get_by_role("button", name="Pause for everyone").click()
        await asyncio.sleep(2)
        rows = await sample(everyone)
        spread = report("after pause", rows)
        check(all(r["state"] == PAUSED for r in rows), "every player paused")
        check(spread < 0.8, f"paused at the same spot ({spread:.2f}s apart)")

        print("\nDJ seeks to 1:30 while paused, then plays")
        await dj.evaluate("""() => { const i = document.querySelector('.progress input[type=range]');
            const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
            set.call(i, '90'); i.dispatchEvent(new Event('input', {bubbles: true}));
            i.dispatchEvent(new MouseEvent('mouseup', {bubbles: true})); }""")
        await asyncio.sleep(2)
        rows = await sample(everyone)
        report("after seek (paused)", rows)
        check(all(abs(r["t"] - 90) < 1.0 for r in rows), "every player moved to 1:30")
        await dj.get_by_role("button", name="Play for everyone").click()
        await asyncio.sleep(6)
        rows = await sample(everyone)
        spread = report("playing after seek", rows)
        check(all(r["state"] == PLAYING and r["t"] > 90 for r in rows), "every player resumed past 1:30")
        check(spread < 0.6, f"still together after seek ({spread:.2f}s apart)")

        print("\nDJ skips to the next song")
        before = rows[0]["vid"]
        await dj.get_by_role("button", name="Next song").click()
        await asyncio.sleep(8)
        rows = await sample(everyone)
        spread = report("after next", rows)
        vids = [r["vid"] for r in rows]
        check(all(v != before for v in vids) and len(set(vids)) == 1, f"every player switched to the same new song ({before} -> {vids})")
        check(spread < 0.6, f"together on the new song ({spread:.2f}s apart)")

        print("\nA listener joins late")
        late = await open_person(browser, base, room, None, "Latecomer")
        await asyncio.sleep(10)
        rows = await sample([dj, late])
        spread = report("late joiner vs DJ", rows)
        check(spread < 0.6, f"late joiner lands in sync ({spread:.2f}s apart)")

        await browser.close()

    print(f"\n{'All sync checks passed' if not failures else f'{len(failures)} check(s) failed'}")
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:5173")
    parser.add_argument("--listeners", type=int, default=2)
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.base, args.listeners)))
