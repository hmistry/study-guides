"""Headless browser checks for dist/study-guide-sqldb.html. Run after `python3 build.py`.

usage: python3 tests/ui_check.py      (needs: pip install playwright && playwright install chromium)
Screenshots go to a temp folder printed at the end. One section shows at a time (hash routing),
so navigate (`goto(pg, "#id")`) before touching anything on a page.
"""
import asyncio, json, pathlib, sys, tempfile
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
SP = pathlib.Path(tempfile.mkdtemp(prefix="sq-ui-check-"))
URL = (ROOT / "dist" / "study-guide-sqldb.html").as_uri()
res = []
def ok(name, cond): res.append(bool(cond)); print(("✓ " if cond else "✗ ") + name)
async def goto(pg, h):
    await pg.evaluate(f"location.hash = {json.dumps(h)}"); await pg.wait_for_timeout(120)
visible_secs = lambda pg: pg.evaluate("[...document.querySelectorAll('#main > .sec')].filter(s => !s.hidden).map(s => s.id)")
hidden = lambda pg, sel: pg.locator(sel).evaluate("e => e.hidden || getComputedStyle(e).display === 'none'")


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1280, "height": 900})
        pg = await ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await pg.goto(URL)

        # 1 pages + routing
        ok("lands on home, only home visible", await visible_secs(pg) == ["home"])
        order = await pg.evaluate("PAGES")
        topics = await pg.evaluate("CAT.filter(c => TOPICS[c.id]).map(c => c.id)")
        ok(f"page order: home, cheat, dataset, topics, drill, glossary ({len(order)} pages)",
           order == ["home", "cheat", "dataset"] + topics + ["drill", "glossary"])
        ok("brand is the accent colour", await pg.locator(".brand").evaluate("e => getComputedStyle(e).color") == "rgb(11, 106, 135)")
        ok("home lists all 17 topics (unwritten as soon)", await pg.locator("#home .pcard").count() == 17
           and await pg.locator("#home .pcard.soon").count() == 17 - len(topics))
        await pg.keyboard.press("ArrowRight"); await pg.wait_for_timeout(120)
        ok("→ key → cheat sheet, nav active", await visible_secs(pg) == ["cheat"]
           and "active" in await pg.get_attribute('.side a[data-pid="cheat"]', "class"))
        await goto(pg, "#repeat-within-10-days")
        ok("problem hash opens its topic page", await visible_secs(pg) == ["windows"])

        # 2 dataset page: tables come from the build, script downloads
        await goto(pg, "#dataset")
        ok("dataset: 6 tables with rows", await pg.locator("#dataset .dtab").count() == 6
           and await pg.locator("#ds-orders .res tbody tr").count() == 15)
        ok("NULL cells render as NULL", await pg.locator("#ds-users .res td.nul").count() >= 1)
        async with pg.expect_download() as dl:
            await pg.click("[data-act=downloadDataset]")
        d = await dl.value
        ok("Download dataset.sql gives the script", d.suggested_filename == "dataset.sql"
           and "CREATE DATABASE practice" in pathlib.Path(await d.path()).read_text())

        # 3 problem: expected result shown first, solution hidden until reveal, attempt persists + highlights
        await goto(pg, "#windows")
        pr = "#running-revenue"
        ok("solution hidden before reveal", await hidden(pg, f"{pr} .pane.sol") and await hidden(pg, f"{pr} .after"))
        await pg.click(f"{pr} summary:has-text('Expected result')")
        ok("expected result table: 9 rows", await pg.locator(f"{pr} .disclose .res tbody tr").count() == 9)
        ta = pg.locator(f"{pr} textarea")
        await ta.click(); await pg.keyboard.type("SELECT day")
        await pg.keyboard.press("Enter"); await pg.keyboard.press("Tab"); await pg.keyboard.type("FROM orders")
        ok("editor: Tab indents two spaces", await ta.input_value() == "SELECT day\n  FROM orders")
        ok("editor: highlight layer tracks the text", "FROM" in await pg.locator(f"{pr} .ed-hl").inner_text()
           and await pg.locator(f"{pr} .ed-hl .token.keyword").count() >= 2)
        await pg.click(f"{pr} .reveal")
        cols = await pg.locator(f"{pr} .work").evaluate("e => getComputedStyle(e).gridTemplateColumns.split(' ').length")
        ok("reveal shows attempt and solution side by side + insight", cols == 2 and not await hidden(pg, f"{pr} .pane.sol")
           and not await hidden(pg, f"{pr} .after"))
        await pg.reload(); await pg.wait_for_timeout(200); await goto(pg, "#windows")
        ok("attempt survives reload", await pg.locator(f"{pr} textarea").input_value() == "SELECT day\n  FROM orders")
        ok("storage uses the sq. prefix only", await pg.evaluate("Object.keys(localStorage).every(k => k.startsWith('sq.'))"))

        # 4 diagrams: table, plan and timeline frames switch
        fig = pg.locator("#windows .fig")
        await fig.locator("[data-frame='1']").click()
        ok("table diagram: frame 2 shows peers in frame", await fig.locator("div[data-fr='1']").is_visible()
           and await fig.locator("div[data-fr='1'] tr.win").count() == 2 and await fig.locator("div[data-fr='1'] tr.cur").count() == 1)
        await goto(pg, "#indexes")
        fig = pg.locator("#indexes .fig")
        await fig.locator("[data-frame='2']").click()
        ok("plan diagram: composite frame has one good node, no sort", await fig.locator("div[data-fr='2'] .plan li.good").count() == 1
           and "Sort" not in await fig.locator("div[data-fr='2'] .plan").inner_text())
        await goto(pg, "#isolation")
        fig = pg.locator("#isolation .fig")
        await fig.locator("[data-frame='4']").click()
        ok("timeline diagram: serializable frame ends in a T2 error", await fig.locator("div[data-fr='4'] td.m-error").count() == 1
           and "40001" in await fig.locator("div[data-fr='4'] td.m-error").inner_text())

        # 5 DDL problem lists its checks before reveal
        await goto(pg, "#indexes")
        ok("DDL problem shows its 5 checks with outcomes", await pg.locator("#one-cart-per-user .tests li").count() == 5
           and await pg.locator("#one-cart-per-user .texp.err").count() == 2)

        # 6 progress: problems + Part B topics are units
        n_units = await pg.evaluate("UNITS.length")
        await pg.click("#one-cart-per-user .st[data-st=done]")
        ok("Got it on a problem → 1 / N, topic dot partly done", await pg.inner_text("#progText") == f"1 / {n_units}"
           and "st-part" in await pg.get_attribute('.side [data-dot="indexes"]', "class"))
        await pg.click("#indexes .p-head .st[data-st=review]")
        ok("Review again on a topic → home review list", "st-review" in await pg.get_attribute('.side [data-dot="indexes"]', "class")
           and await pg.locator("#reviewList a[href='#indexes']").count() == 1)
        await pg.click("#indexes .p-head .st[data-st=review]"); await pg.click("#one-cart-per-user .st[data-st=done]")
        ok("clicking again clears both", await pg.inner_text("#progText") == f"0 / {n_units}")

        # 7 site pages
        await goto(pg, "#cheat")
        ok("cheat sheet: 17 topic rows linking to pages", await pg.locator("#cheat td.nm a").count() == 17)
        ok("cheat sheet: syntax groups rendered", await pg.locator("#cheat td.sx").count() >= 25)
        await pg.evaluate("window.print = () => { window.__printed = document.body.classList.contains('print-cheat'); }")
        await pg.click("#cheat [data-act=printCheat]")
        ok("print button prints the cheat sheet alone", await pg.evaluate("window.__printed === true"))
        await pg.evaluate("document.body.classList.remove('print-cheat')")
        await goto(pg, "#drill")
        await pg.keyboard.press("1")
        ok("drill: key 1 answers and shows the verdict", await pg.locator("#drillCard .verdict:not([hidden])").count() == 1
           and await pg.locator("#drillCard .opt.right").count() == 1)
        await pg.keyboard.press("Enter"); await pg.wait_for_timeout(80)
        ok("drill: Enter goes to question 2", "Question 2" in await pg.inner_text("#drillCard .drill-h"))
        await goto(pg, "#glossary")
        n_terms = await pg.locator(".gl-row").count()
        terms = await pg.locator(".gl-term").all_inner_texts()
        ok(f"glossary: {n_terms} terms, sorted A–Z", n_terms >= 60 and terms == sorted(terms, key=str.lower))
        await pg.fill("#glFilter", "wraparound")
        ok("glossary filter narrows rows", 1 <= await pg.locator(".gl-row:not([hidden])").count() < 6)
        await pg.fill("#glFilter", "zzzz")
        ok("glossary: empty-filter message", await pg.locator("#glEmpty").is_visible())

        # 8 more diagrams: 3-session timeline, shell snippets
        await goto(pg, "#locking")
        fig = pg.locator("#locking .fig")
        await fig.locator("[data-frame='2']").click()
        ok("timeline frame with its own 3 sessions", await fig.locator("div[data-fr='2'] .tl th").count() == 4
           and await fig.locator("div[data-fr='0'] .tl th").count() == 3)
        await goto(pg, "#setup-ddl")
        ok("shell snippet shows $ prompts and no SQL highlighting", await pg.locator("#setup-ddl pre.shell .ps").count() >= 4
           and await pg.locator("#setup-ddl pre.shell .token").count() == 0)

        # 9 every topic: reveal all opens everything
        for h in topics:
            await goto(pg, "#" + h)
            await pg.click(f"#{h} [data-act=revealAll]")
            n = await pg.locator(f"#{h} .unit").count()
            ok(f"{h}: reveal all opens all {n} units", n and await pg.locator(f"#{h} .unit.open").count() == n)
            await pg.screenshot(path=SP / f"{h}.png", full_page=True)

        # 8 mobile: no horizontal page scroll on any page
        m = await b.new_page(viewport={"width": 390, "height": 844})
        m.on("pageerror", lambda e: errs.append(str(e)))
        await m.goto(URL)
        for h in order:
            await goto(m, "#" + h)
            if await m.locator(f"#{h} [data-act=revealAll]").count():
                await m.locator(f"#{h} [data-act=revealAll]").first.click()
            w = await m.evaluate("document.documentElement.scrollWidth")
            ok(f"mobile {h}: no page overflow ({w}px)", w <= 390)
            await m.screenshot(path=SP / f"m-{h}.png", full_page=True)

        ok(f"no JS errors {errs}", not errs)
        await b.close()
    print(f"\n{sum(res)}/{len(res)} passed · screenshots in {SP}")
    sys.exit(0 if all(res) else 1)

asyncio.run(main())
