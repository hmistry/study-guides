"""Headless browser checks for dist/study-guide-sysd.html. Run after `python3 build.py`.

usage: python3 tests/ui_check.py      (needs: pip install playwright && playwright install chromium)
Screenshots go to a temp folder printed at the end. One section shows at a time (hash routing),
so navigate (`goto(pg, "#id")`) before touching anything on a page.
"""
import asyncio, json, pathlib, sys, tempfile
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
SP = pathlib.Path(tempfile.mkdtemp(prefix="sd-ui-check-"))
URL = (ROOT / "dist" / "study-guide-sysd.html").as_uri()
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
        built = await pg.evaluate("DATA.blocks.length + DATA.cases.length")
        ok(f"page order: home, cheat, framework, blocks, cases, drills, glossary ({len(order)} pages)",
           order == ["home", "cheat", "framework"] + await pg.evaluate("[...DATA.blocks, ...DATA.cases].map(x => x.id)")
           + ["est-drill", "drill", "glossary"])
        ok("brand is the accent colour", await pg.locator(".brand").evaluate("e => getComputedStyle(e).color") == "rgb(11, 106, 135)")
        ok("home lists 16 blocks + 12 cases (unwritten as soon)", await pg.locator("#home .pcard").count() == 28
           and await pg.locator("#home .pcard.soon").count() == 28 - built)
        await pg.keyboard.press("ArrowRight"); await pg.wait_for_timeout(120)
        ok("→ key → cheat sheet, nav active", await visible_secs(pg) == ["cheat"]
           and "active" in await pg.get_attribute('.side a[data-pid="cheat"]', "class"))
        await goto(pg, "#url-shortener--codes")
        ok("deep-dive hash opens its case page", await visible_secs(pg) == ["url-shortener"])

        # 2 block: checks hidden first, numeric checker, reveal all
        await goto(pg, "#estimation")
        c1 = "#estimation--check-1"
        ok("answer hidden before reveal", await hidden(pg, f"{c1} .ans-solo"))
        ok("reference numbers hidden before reveal", await pg.locator(f"{c1} .cans:not([hidden])").count() == 0)
        inp = pg.locator(f"{c1} input").first
        await inp.fill("12K"); await pg.click(f"{c1} [data-act=check]")
        ok("12K for 11.6K → close", "close" in await pg.locator(f"{c1} .cv").first.inner_text())
        await inp.fill("1200"); await inp.press("Enter")
        v = await pg.locator(f"{c1} .cv").first.inner_text()
        ok(f"1200 for 11.6K → off ({v})", "off" in v and "low" in v)
        await inp.fill("2e4"); await inp.press("Enter")
        ok("2e4 → ballpark", "ballpark" in await pg.locator(f"{c1} .cv").first.inner_text())
        await pg.click(f"{c1} .reveal")
        ok("reveal shows answer and all reference numbers", not await hidden(pg, f"{c1} .ans-solo")
           and await pg.locator(f"{c1} .cans:not([hidden])").count() == 2)
        await pg.click("#estimation [data-act=revealAll]")
        ok("reveal all opens every check", await pg.locator("#estimation .unit.open").count() == await pg.locator("#estimation .unit").count()
           and await pg.locator("#estimation [data-act=revealAll]").inner_text() == "Hide all")
        await pg.click("#estimation [data-act=revealAll]")
        ok("hide all closes them", await pg.locator("#estimation .unit.open").count() == 0)

        # 3 diagram frames
        await goto(pg, "#caching")
        fig = pg.locator("#caching .arch")
        await fig.locator("[data-frame='2']").click()
        ok("frame tab switches drawing and note", await fig.locator("div[data-fr='2']").is_visible()
           and not await fig.locator("div[data-fr='0']").is_visible() and "delete" in await fig.locator("p[data-fr='2']").inner_text())

        # 4 case: step by step, notes persist, reveal all hides empty notes
        await goto(pg, "#url-shortener")
        req = "#url-shortener--requirements"
        ok("every reference hidden at first", await pg.locator("#url-shortener .pane.ans:not([hidden])").count() == 0)
        ok("HLD diagram hidden before reveal", await hidden(pg, "#url-shortener--high-level .ans-wide"))
        await pg.fill(f"{req} textarea", "read-heavy 100:1")
        await pg.click(f"{req} .reveal")
        cols = await pg.locator(f"{req} .work").evaluate("e => getComputedStyle(e).gridTemplateColumns.split(' ').length")
        ok("revealed step shows notes and reference side by side", cols == 2 and not await hidden(pg, f"{req} .pane.ans"))
        ok("toc marks the step seen", "seen" in await pg.get_attribute('[data-toc="url-shortener.requirements"]', "class"))
        await pg.click("#url-shortener [data-act=revealAll]")
        units = await pg.locator("#url-shortener .unit").count()
        ok(f"reveal all opens all {units} units (7 steps → 6 + 6 deep dives)", units == 12
           and await pg.locator("#url-shortener .unit.open").count() == units)
        ok("review mode hides empty notes, keeps written ones", await hidden(pg, "#url-shortener--api .notes")
           and not await hidden(pg, f"{req} .notes"))
        ok("HLD diagram shown in reveal all", not await hidden(pg, "#url-shortener--high-level .ans-wide"))
        await pg.reload(); await pg.wait_for_timeout(200)
        ok("notes survive reload", await pg.locator(f"{req} textarea").input_value() == "read-heavy 100:1")
        ok("storage uses the sd. prefix only", await pg.evaluate("Object.keys(localStorage).every(k => k.startsWith('sd.'))"))

        # 5 progress
        await pg.click("#url-shortener .st[data-st=done]")
        ok("Got it → top bar 1 / N and sidebar dot", await pg.inner_text("#progText") == f"1 / {built}"
           and "st-done" in await pg.get_attribute('.side [data-dot="url-shortener"]', "class"))
        await pg.click("#url-shortener .st[data-st=done]")
        ok("clicking again clears it", await pg.inner_text("#progText") == f"0 / {built}")
        await pg.screenshot(path=SP / "case.png", full_page=True)

        # 6 mobile: no horizontal page scroll on any page
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

        # 7 site pages
        await goto(pg, "#cheat")
        ok("cheat sheet: 16 block rows + 12 case rows, links to pages", await pg.locator("#cheat tbody tr").count() == 28
           and await pg.locator("#cheat td.nm a").count() == 28)
        await pg.evaluate("window.print = () => { window.__printed = document.body.classList.contains('print-cheat'); }")
        await pg.click("#cheat [data-act=printCheat]")
        ok("print button prints the cheat sheet alone", await pg.evaluate("window.__printed === true"))
        await pg.evaluate("document.body.classList.remove('print-cheat')")
        await goto(pg, "#framework")
        ok("framework: 7 steps, time bar totals 45 min", await pg.locator("#framework .fstep").count() == 7
           and "45 min" in await pg.locator("#framework").evaluate("e => e.textContent"))
        await pg.click("#framework .tbar a >> nth=5")
        ok("time-bar segment jumps to its step", await pg.evaluate("location.hash") == "#fw-deep-dives")
        await goto(pg, "#est-drill")
        e1 = "#est-drill--1"
        await pg.fill(f"{e1} input >> nth=0", "120"); await pg.press(f"{e1} input >> nth=0", "Enter")
        ok("estimation drill checks numbers", "close" in await pg.locator(f"{e1} .cv").first.inner_text())
        await goto(pg, "#drill")
        await pg.keyboard.press("1")
        ok("block drill: key 1 answers and shows the verdict", await pg.locator("#drillCard .verdict:not([hidden])").count() == 1
           and await pg.locator("#drillCard .opt.right").count() == 1)
        await pg.keyboard.press("Enter"); await pg.wait_for_timeout(80)
        ok("Enter goes to question 2", "Question 2" in await pg.inner_text("#drillCard .drill-h"))
        await goto(pg, "#glossary")
        n_terms = await pg.locator(".gl-row").count()
        terms = await pg.locator(".gl-term").all_inner_texts()
        ok(f"glossary: {n_terms} terms, sorted A–Z", n_terms >= 40 and terms == sorted(terms, key=str.lower))
        await pg.fill("#glFilter", "fencing")
        ok("glossary filter narrows rows", await pg.locator(".gl-row:not([hidden])").count() >= 1
           and await pg.locator(".gl-row:not([hidden])").count() < 5 and "of" in await pg.inner_text("#glCount"))
        await pg.fill("#glFilter", "zzzz")
        ok("empty filter message", await pg.locator("#glEmpty").is_visible())

        # every page: diagrams render, every reveal-all opens everything
        for h in order[1:]:
            await goto(pg, "#" + h)
            for btn in await pg.locator(f"#{h} [data-act=revealAll]").all():
                if await btn.inner_text() == "Reveal all":
                    await btn.click()
            n_units = await pg.locator(f"#{h} .unit").count()
            if n_units:
                ok(f"{h}: all {n_units} units open after reveal all", await pg.locator(f"#{h} .unit.open").count() == n_units)

        ok(f"no JS errors {errs}", not errs)
        await b.close()
    print(f"\n{sum(res)}/{len(res)} passed · screenshots in {SP}")
    sys.exit(0 if all(res) else 1)

asyncio.run(main())
