"""Headless browser checks for dist/study-guide-algo.html. Run after `python3 build.py`.

usage: python3 tests/ui_check.py      (needs: pip install playwright && playwright install chromium)
Screenshots go to a temp folder printed at the end. The page shows one section at a time (hash routing),
so navigate (`goto(pg, "#id")`) before touching anything on a section.
"""
import asyncio, json, pathlib
from playwright.async_api import async_playwright
import sys, tempfile
ROOT = pathlib.Path(__file__).resolve().parent.parent
SP = pathlib.Path(tempfile.mkdtemp(prefix="ui-check-"))
URL = (ROOT / "dist" / "study-guide-algo.html").as_uri()
res = []
def ok(name, cond): res.append(cond); print(("✓ " if cond else "✗ ") + name)
async def goto(pg, h):
    await pg.evaluate(f"location.hash = {json.dumps(h)}"); await pg.wait_for_timeout(120)
visible_secs = lambda pg: pg.evaluate("[...document.querySelectorAll('#main > .sec')].filter(s => !s.hidden).map(s => s.id)")
text = lambda loc: loc.evaluate("e => e.textContent")

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True)
        pg = await ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await pg.goto(URL)

        # 1 pages + routing
        ok("lands on home, only home visible", await visible_secs(pg) == ["home"])
        total = await pg.locator(".prob").count()
        ok(f"32 problems rendered ({total})", total == 32)
        ok("16 pattern sections, each with a diagram", await pg.locator("section.pattern").count() == 16
           and await pg.locator("section.pattern .diagram svg").count() == 16)
        order = await pg.evaluate("PAGES")
        ok("page order: home, cheat, 16 patterns, drill, decision, lang-sheet",
           order[:3] == ["home", "cheat", "two-pointers"] and order[-3:] == ["drill", "decision", "lang-sheet"] and len(order) == 21)
        ok("Python vs Ruby page retired", await pg.locator("#langs").count() == 0)
        ok("brand is the accent colour", await pg.locator(".brand").evaluate("e => getComputedStyle(e).color") == "rgb(11, 106, 135)")
        await pg.click("#home .pager .next")
        await pg.wait_for_timeout(120)
        ok("next button → cheat sheet", await visible_secs(pg) == ["cheat"])
        await pg.keyboard.press("ArrowRight"); await pg.wait_for_timeout(120)
        ok("→ key → two pointers, nav active", await visible_secs(pg) == ["two-pointers"]
           and "active" in await pg.get_attribute('.side .pl[data-pid="two-pointers"]', "class"))
        await pg.keyboard.press("ArrowLeft"); await pg.wait_for_timeout(120)
        ok("← key → back to cheat sheet", await visible_secs(pg) == ["cheat"])
        await goto(pg, "#three-sum")
        ok("problem link opens its pattern page", await visible_secs(pg) == ["two-pointers"] and await pg.locator("#three-sum").is_visible())
        prev = await pg.locator("#two-pointers .pager a").all_inner_texts()
        ok(f"pager labels {prev}", prev == ["← Cheat Sheet", "Sliding Window →"])

        # 2 reveal still hidden-first; test cases
        ok("solution hidden before reveal", not await pg.locator("#two-sum-ii .pane.sol").is_visible())
        await pg.click("#three-sum .disclose details:nth-child(2) summary")
        tc = await pg.locator("#three-sum .tc li").all_inner_texts()
        ok(f"3sum test cases shown ({len(tc)})", len(tc) == 5 and "three_sum([-1, 0, 1, 2, -1, -4])" in tc[0])
        await pg.click(".lang button[data-lang=ruby]")
        ok("test cases re-render on lang switch", "three_sum" in (await pg.locator("#three-sum .tc li").first.inner_text()))
        await pg.click(".lang button[data-lang=python]")

        # 3 editor highlighting
        ta = pg.locator("#two-sum-ii textarea")
        await ta.click(); await pg.keyboard.press("End"); await pg.keyboard.type("\nreturn [1, 2]  # done")
        hl = pg.locator("#two-sum-ii .ed-hl")
        ok("attempt is syntax-highlighted as you type", await hl.locator(".token.keyword").count() >= 2 and await hl.locator(".token.comment").count() == 1)
        ok("textarea text itself is transparent", await ta.evaluate("e => getComputedStyle(e).webkitTextFillColor") in ("rgba(0, 0, 0, 0)", "transparent"))

        # 4 progress: card buttons, sidebar dots, top bar, home
        await pg.click("#two-sum-ii .st[data-st=done]")
        await pg.click("#three-sum .st[data-st=review]")
        ok("top bar progress", (await pg.inner_text("#progText")) == f"1 / {total}")
        ok("sidebar dot done", "st-done" in (await pg.get_attribute('.ql[data-prob="two-sum-ii"]', "class")))
        await goto(pg, "#home")
        ok("home stats", (await pg.inner_text("#homeStats .stats b")) == f"1 / {total}")
        ok("home review list has 3Sum", (await pg.locator("#reviewList a").all_inner_texts()) == ["3Sum"])
        ok("continue → first unfinished", (await pg.get_attribute("#continue", "href")) == "#three-sum")
        ok("pattern grid dots", await pg.locator("#patternGrid .dot.st-done").count() == 1 and await pg.locator("#patternGrid .dot.st-review").count() == 1)
        await goto(pg, "#two-pointers")
        await pg.click("#three-sum .st[data-st=review]")   # toggle off
        ok("status toggles off", (await pg.get_attribute("#three-sum .st[data-st=review]", "aria-pressed")) == "false")

        # 5 backup export/import round trip
        await goto(pg, "#sliding-window")
        await pg.locator("#max-sum-k textarea").fill("def max_sum_subarray(nums, k):\n    return 42")
        await pg.locator("#max-sum-k textarea").dispatch_event("input")
        await goto(pg, "#home")
        async with pg.expect_download() as d:
            await pg.click("[data-act=exportAll]")
        f = SP / "backup.json"; await (await d.value).save_as(f)
        blob = json.loads(f.read_text())
        ok(f"export has app/version + attempt + progress ({len(blob['data'])} keys)", blob.get("app") == "algo-patterns" and blob.get("version") == 1
           and "sg.att.max-sum-k.python" in blob["data"] and blob["data"].get("sg.prog.two-sum-ii") == "done")
        pg2 = await (await b.new_context(viewport={"width": 1280, "height": 900})).new_page()
        pg2.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await pg2.goto(URL)
        await pg2.set_input_files("#importFile", str(f)); await pg2.wait_for_timeout(400)
        ok("import restores attempt", "return 42" in await pg2.locator("#max-sum-k textarea").input_value())
        ok("import restores progress", (await pg2.inner_text("#progText")) == f"1 / {total}")
        ok("import re-highlights the editor", "42" in await text(pg2.locator("#max-sum-k .ed-hl")))

        # 6 reset all (dialogs auto-accepted)
        await pg2.click("[data-act=resetAll]"); await pg2.wait_for_timeout(600)
        keys = await pg2.evaluate("Object.keys(localStorage).filter(k => k.startsWith('sg.'))")
        ok(f"reset clears all sg.* keys ({keys})", keys == [])
        ok("after reset: 0 done, attempt back to stub", (await pg2.inner_text("#progText")) == f"0 / {total}"
           and "return 42" not in await pg2.locator("#max-sum-k textarea").input_value())

        # 7 node / op-sequence test cases, Provided panel, diagrams
        await goto(pg, "#linked-list-cycle")
        tc = await pg.locator("#linked-list-cycle .tc li").evaluate_all("ls => ls.map(l => l.textContent)")
        ok("node test case rendered", tc and tc[0].startswith("has_cycle(list[3, 2, 0, -4] pos=1) → True"))
        ok("Provided panel only where used", await pg.locator("#linked-list-cycle [data-src^='n:']").count() == 1
           and await pg.locator("#find-duplicate [data-src^='n:']").count() == 0)
        prov = lambda pid: text(pg.locator(f"#{pid} [data-src^='n:']"))
        ok("op-sequence test case", (await text(pg.locator("#implement-trie .tc li").first)).startswith('obj = Trie(); obj.insert("apple")'))
        await goto(pg, "#heap")
        await pg.click(".lang button[data-lang=ruby]")
        mk = await prov("merge-k-lists")
        ok("ruby Provided: ListNode + MinHeap", "class ListNode" in mk and "class MinHeap" in mk)
        await pg.click("#kth-largest .reveal")
        async with pg.expect_download() as d:
            await pg.click("#kth-largest [data-act=export][data-which=sol]")
        f = SP / "kth.rb"; await (await d.value).save_as(f)
        ok("exported ruby heap solution includes MinHeap", f.read_text().startswith("# Ruby has no heap") and "def find_kth_largest" in f.read_text())
        await pg.click("#kth-largest .reveal")
        await pg.click(".lang button[data-lang=python]")
        ok("python Provided for heap: heapq note", "heapq is built in" in await prov("kth-largest"))
        ok("tree / grid / graph diagrams", await pg.locator("#trie .diagram rect").count() == 10
           and await pg.locator("#dp-2d .diagram rect").count() == 48 and await pg.locator("#topo-sort .diagram circle").count() == 12)
        ok("linked diagram: 18 nodes", await pg.locator("#fast-slow .diagram circle").count() == 18)
        ok("intervals diagram: 7 bars + cut", await pg.locator("#merge-intervals .diagram rect").count() == 7
           and await pg.locator("#merge-intervals .diagram .d-cut").count() == 1)

        # 8 drill (keys only act on the drill page)
        await goto(pg, "#drill")
        q1 = await pg.inner_text("#drillCard .drill-q")
        await pg.keyboard.press("1"); await pg.wait_for_timeout(100)
        ok("drill answers via key + shows verdict", await pg.locator("#drillCard .verdict").is_visible())
        ok("correct option highlighted", await pg.locator("#drillCard .opt.right").count() == 1)
        await pg.keyboard.press("Enter"); await pg.wait_for_timeout(100)
        ok("Enter advances", (await pg.inner_text("#drillCard .drill-h span")) == "Question 2 / 16" and await pg.inner_text("#drillCard .drill-q") != q1)
        await goto(pg, "#cheat")
        await pg.keyboard.press("2"); await pg.wait_for_timeout(100)
        ok("drill keys ignored off the drill page", not await pg.locator("#drillCard .verdict").is_visible())

        # 9 language cheat sheet
        await goto(pg, "#ls-strings")
        ok("section link opens the cheat sheet page", await visible_secs(pg) == ["lang-sheet"])
        rows = lambda: pg.locator("#lang-sheet .ls-row").count()
        n_py = await rows()
        has = lambda t: pg.locator("#lang-sheet .ls-task", has_text=t).count()
        ok(f"python rows ({n_py}); ruby-only rows hidden", n_py >= 150 and await has("case / when") == 0 and await has("Mutable default argument") == 1)
        await pg.click(".lang button[data-lang=ruby]")
        n_rb = await rows()
        ok(f"ruby rows ({n_rb}); python-only rows hidden", n_rb >= 150 and await has("case / when") == 1 and await has("Mutable default argument") == 0)
        ok("ruby code + result rendered", "s.reverse" in await text(pg.locator("#ls-strings")) and '"dlroW ,olleH"' in await text(pg.locator("#ls-strings")))
        ok("traps flagged", await pg.locator("#lang-sheet .ls-row.trap").count() >= 5)
        sh = pg.locator("#ls-setup pre.shell", has_text="bundle install")
        ok("shell rows: $ prompt, shell tag, not highlighted", await sh.count() == 1 and (await text(sh)).startswith("$ bundle init")
           and await pg.locator("#ls-setup .shtag").count() >= 3 and await sh.locator(".token").count() == 0)
        beside = await pg.evaluate("""[...document.querySelectorAll('#lang-sheet .ls-row')].filter(r => {
            const pre = r.querySelector('pre'), out = r.querySelector('.ls-out');
            return r.offsetParent && (pre.offsetWidth < pre.parentElement.clientWidth - 1
              || (out && out.getBoundingClientRect().top < pre.getBoundingClientRect().bottom - 1)); }).length""")
        ok(f"code full width, result on its own line ({beside} violations)", beside == 0)
        await pg.fill("#lsFilter", "split")
        shown = await pg.locator("#lang-sheet .ls-row:not([hidden])").count()
        ok(f"filter narrows rows ({shown}) and hides empty sections", 0 < shown < 15 and await pg.locator("#ls-basics").is_hidden()
           and (await pg.inner_text("#lsCount")).startswith(f"{shown} of"))
        await pg.fill("#lsFilter", "zzzz-nothing")
        ok("no-match message", await pg.locator("#lsEmpty").is_visible())
        await pg.fill("#lsFilter", "")
        await pg.click(".lang button[data-lang=python]")
        ok("filter cleared → all rows back", await rows() == n_py and not await pg.locator("#lsEmpty").is_visible())

        # 10 sections render
        ok("decision cards", await pg.locator(".dcard").count() == 11)
        ok("cheat rows", await pg.locator("#cheat tbody tr").count() == 16)
        for h in ["home", "cheat", "two-pointers", "dp-2d", "drill", "decision", "lang-sheet"]:
            await goto(pg, "#" + h); await pg.screenshot(path=SP/f"{h}.png", full_page=True)
        await goto(pg, "#cheat")
        await pg.evaluate("document.body.classList.add('print-cheat')")
        await pg.pdf(path=str(SP/"cheat.pdf"), format="Letter")
        m = await b.new_page(viewport={"width": 390, "height": 844}); await m.goto(URL)
        no_scroll = True
        for h in ["home", "two-pointers", "dp-2d", "decision", "lang-sheet"]:
            await goto(m, "#" + h)
            no_scroll &= not await m.evaluate("document.documentElement.scrollWidth > innerWidth")
        ok("mobile no h-scroll", no_scroll)
        await goto(m, "#home"); await m.screenshot(path=SP/"mobile-home.png")
        ok(f"no JS errors {errs}", not errs)
        await b.close()
    print("screenshots:", SP)
    print("ALL PASS" if all(res) else "FAILURES")
    sys.exit(0 if all(res) else 1)
asyncio.run(main())
