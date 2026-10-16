#!/usr/bin/env python3
"""Validate guide.yaml + blocks/*.yaml + cases/*.yaml + pages/*.yaml, recompute every estimate, then render one offline HTML file.

usage: python3 build.py [-o OUT.html]
"""
import argparse, ast, json, math, operator, pathlib, re, sys
import yaml

ROOT = pathlib.Path(__file__).parent
BLOCK_KEYS = {"id", "name", "signal", "idea", "diagram", "numbers", "tables", "pitfalls", "depth", "checks"}
BLOCK_REQUIRED = {"id", "name", "signal", "idea", "pitfalls", "depth", "checks"}
CASE_KEYS = {"id", "name", "prompt", "blocks", "steps"}
STEP_KEYS = {"id", "title", "min", "ask", "answer", "given", "calc", "diagram", "items"}
KINDS = {"client", "service", "db", "cache", "queue"}
ARCH_AX, ARCH_NW = 216, 116   # template.html AX / NW: column pitch and box width
errors = []


def err(where, msg):
    errors.append(f"✗ {where}: {msg}")


# ── estimates: a tiny arithmetic evaluator (no names beyond `given`, earlier calc names and a few functions)
OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
       ast.Pow: operator.pow, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.USub: operator.neg, ast.UAdd: operator.pos}
FUNCS = {"min": min, "max": max, "ceil": math.ceil, "log2": math.log2}


def evaluate(expr, env):
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.Name):
            if n.id not in env:
                raise ValueError(f"unknown name {n.id!r}")
            return env[n.id]
        if isinstance(n, ast.BinOp) and type(n.op) in OPS:
            return OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in OPS:
            return OPS[type(n.op)](ev(n.operand))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in FUNCS:
            return FUNCS[n.func.id](*map(ev, n.args))
        raise ValueError(f"unsupported syntax: {ast.dump(n)[:60]}")
    return ev(ast.parse(str(expr), mode="eval"))


SUFFIX = {"K": 1e3, "k": 1e3, "M": 1e6, "B": 1e9, "G": 1e9, "T": 1e12}


def shown_number(s):
    """'≈ 12K/s' → 12000; '3 TB' → 3 (a suffix must touch the digits; a spaced unit is just a unit)."""
    m = re.search(r"(\d[\d,]*(?:\.\d+)?(?:e[+-]?\d+)?)([KkMBGT](?![A-Za-z]))?", s)
    if not m:
        return None
    return float(m.group(1).replace(",", "")) * SUFFIX.get(m.group(2) or "", 1)


def check_calc(where, unit):
    """Evaluate `given` and every `calc` row in order; store `value` on each row for the page."""
    env = {}
    for k, v in (unit.get("given") or {}).items():
        try:
            env[k] = evaluate(v, env) if isinstance(v, str) else v
        except Exception as e:
            err(where, f"given {k}: {e}")
    for i, row in enumerate(unit["calc"]):
        missing = {"ask", "expr", "show"} - set(row)
        if missing:
            err(f"{where} calc[{i}]", f"missing {sorted(missing)}")
            continue
        try:
            v = float(evaluate(row["expr"], env))
        except Exception as e:
            err(f"{where} calc[{i}]", f"{row['expr']!r}: {e}")
            continue
        row["value"] = v
        if row.get("name"):
            env[row["name"]] = v
        shown = shown_number(str(row["show"]))
        if shown is None or abs(shown / v - 1) > 0.15:
            err(f"{where} calc[{i}]", f"show {row['show']!r} disagrees with computed {v:,.4g}")


# ── text: markdown tables must be rectangular
def check_md(where, text):
    if not isinstance(text, str):
        return
    if any(l.startswith((" ", "\t")) and l.strip().startswith("```") for l in text.split("\n")):
        err(where, "indented ``` fence: code blocks must start at column 0 (they can't nest in list items)")
    blocks, cur = [], []
    for l in text.split("\n"):
        if l.strip().startswith("|"):
            cur.append(l.strip())
        elif cur:
            blocks.append(cur); cur = []
    if cur:
        blocks.append(cur)
    for b in blocks:
        widths = [len(l.strip("|").split("|")) for l in b]
        if len(set(widths)) > 1:
            err(where, f"markdown table rows have different cell counts {widths}")


def check_diagram(where, d):
    if d.get("type") != "arch":
        err(where, f"diagram type {d.get('type')!r} (only 'arch' so far)")
        return
    nodes = d.get("nodes") or {}
    if nodes and max(n.get("at", [0])[0] for n in nodes.values()) > 4:
        err(where, "diagram wider than 5 columns (col 0–4); it would render too small")
    for nid, n in nodes.items():
        if "label" not in n or "at" not in n:
            err(where, f"node {nid} needs label and at")
        if n.get("kind", "service") not in KINDS:
            err(where, f"node {nid} kind {n.get('kind')!r}")
        room = ARCH_NW - 12 - (20 if n.get("kind") == "queue" else 0)   # queue glyph takes the right edge
        for field, px in (("label", 7.4), ("sub", 6.4)):
            if len(str(n.get(field, ""))) * px > room:
                err(where, f"node {nid} {field} {n[field]!r} too wide for its box (max ~{int(room / px)} chars)")
    for e in d.get("edges", []):
        for x in e[:2]:
            if x not in nodes:
                err(where, f"edge to unknown node {x!r}")
    if not d.get("frames"):
        err(where, "diagram has no frames")
    for i, f in enumerate(d.get("frames", [])):
        if "title" not in f:
            err(where, f"frame {i} needs a title")
        for e in f.get("flow", []):
            for x in e[:2]:
                if x not in nodes:
                    err(where, f"frame {i} flow to unknown node {x!r}")
            if len(e) > 2 and all(x in nodes for x in e[:2]):
                (c1, r1), (c2, r2) = nodes[e[0]]["at"], nodes[e[1]]["at"]
                gap = abs(c1 - c2) * ARCH_AX - ARCH_NW - 6
                if r1 == r2 and len(str(e[2])) * 6.7 > gap:   # label sits in the gap between two boxes on a row
                    err(where, f"frame {i} label {e[2]!r} too wide for its gap (max ~{int(gap / 6.7)} chars)")
        for x in f.get("hit", []) + f.get("win", []):
            if x not in nodes:
                err(where, f"frame {i} marks unknown node {x!r}")


def check_block(b, file):
    where = f"blocks/{file.name}"
    if b.get("id") != file.stem:
        err(where, f"id {b.get('id')!r} must match the file name")
    if bad := set(b) - BLOCK_KEYS:
        err(where, f"unknown keys {sorted(bad)}")
    if missing := BLOCK_REQUIRED - set(b):
        err(where, f"missing {sorted(missing)}")
        return
    if b.get("diagram"):
        check_diagram(where, b["diagram"])
    for t in b.get("tables", []):
        bad = [r for r in t["rows"] if len(r) != len(t["cols"])]
        if bad:
            err(where, f"table {t['title']!r}: {len(bad)} row(s) don't have {len(t['cols'])} cells")
    for i, c in enumerate(b["checks"]):
        if "q" not in c or not ("a" in c or "calc" in c):
            err(f"{where} checks[{i}]", "needs q and a (text) or calc (numeric)")
        if "calc" in c:
            check_calc(f"{where} checks[{i}]", c)
        check_md(f"{where} checks[{i}]", c.get("a"))


def check_case(c, file, catalog):
    where = f"cases/{file.name}"
    if c.get("id") != file.stem:
        err(where, f"id {c.get('id')!r} must match the file name")
    if bad := set(c) - CASE_KEYS:
        err(where, f"unknown keys {sorted(bad)}")
    for ref in c.get("blocks", []):
        if ref not in catalog:
            err(where, f"unknown block {ref!r}")
    seen = set()
    for s in c.get("steps", []):
        sw = f"{where} step {s.get('id')}"
        if bad := set(s) - STEP_KEYS:
            err(sw, f"unknown keys {sorted(bad)}")
        if not {"id", "title", "min", "ask"} <= set(s):
            err(sw, "needs id, title, min, ask")
        if not ("answer" in s or "items" in s):
            err(sw, "needs answer or items")
        ids = [s.get("id")] + [f"{s.get('id')}.{it.get('id')}" for it in s.get("items", [])]
        for i in ids:
            if i in seen:
                err(sw, f"duplicate id {i}")
            seen.add(i)
        if "calc" in s:
            check_calc(sw, s)
        if "diagram" in s:
            check_diagram(sw, s["diagram"])
        for it in s.get("items", []):
            if not {"id", "q", "answer"} <= set(it):
                err(sw, f"item {it.get('id')} needs id, q, answer")
            check_md(f"{sw}.{it.get('id')}", it.get("answer"))
        check_md(sw, s.get("answer"))
        check_md(sw, s.get("ask"))


def load():
    guide = yaml.safe_load((ROOT / "guide.yaml").read_text())
    data = {"catalog": guide, "blocks": [], "cases": []}
    for kind in ("blocks", "cases"):
        cat = [e["id"] for e in guide[kind]]
        if len(set(cat)) != len(cat):
            err("guide.yaml", f"duplicate {kind} ids")
        files = {f.stem: f for f in sorted((ROOT / kind).glob("*.yaml"))}
        for stem in files.keys() - set(cat):
            err(f"{kind}/{stem}.yaml", "not in guide.yaml catalog")
        for cid in cat:                                   # catalog order = page order
            if cid in files:
                try:
                    item = yaml.safe_load(files[cid].read_text())
                except yaml.YAMLError as e:
                    err(f"{kind}/{cid}.yaml", f"YAML: {e}".replace("\n", " "))
                    continue
                (check_block(item, files[cid]) if kind == "blocks"
                 else check_case(item, files[cid], {e["id"] for e in guide["blocks"]}))
                data[kind].append(item)
    # every page id and step id becomes an HTML id
    ids = [x["id"] for k in ("blocks", "cases") for x in data[k]]
    for i in {i for i in ids if ids.count(i) > 1}:
        err("ids", f"duplicate page id {i}")
    data["pages"] = load_pages(guide, data)
    return data


SITE_PAGES = ("cheat", "framework", "est-drill", "drill", "glossary")


def load_pages(guide, data):
    """Site-wide pages in pages/<name>.yaml; every reference must point at a catalog id."""
    pages = {}
    for name in SITE_PAGES:
        try:
            pages[name] = yaml.safe_load((ROOT / "pages" / f"{name}.yaml").read_text())
        except (OSError, yaml.YAMLError) as e:
            err(f"pages/{name}.yaml", str(e).replace("\n", " "))
            return {}
    blocks, cases = [e["id"] for e in guide["blocks"]], [e["id"] for e in guide["cases"]]
    cheat = pages["cheat"]
    for kind, ids, keys in (("blocks", blocks, {"id", "when", "move", "num"}), ("cases", cases, {"id", "crux", "key"})):
        rows = cheat.get(kind, [])
        if [r.get("id") for r in rows] != ids:
            err("pages/cheat.yaml", f"{kind} rows must list every catalog id once, in catalog order")
        for r in rows:
            if set(r) != keys:
                err("pages/cheat.yaml", f"{kind} row {r.get('id')}: keys must be {sorted(keys)}")
    steps = [s["id"] for s in pages["framework"]["steps"]]
    for c in data["cases"]:
        if [s["id"] for s in c["steps"]] != steps:
            err(f"cases/{c['id']}.yaml", f"steps must follow the framework: {steps}")
    for i, pr in enumerate(pages["est-drill"]["problems"]):
        check_calc(f"pages/est-drill.yaml problems[{i}]", pr)
    for i, it in enumerate(pages["drill"]["items"]):
        opts = [it.get("answer")] + list(it.get("distractors", []))
        if len(opts) != 4 or len(set(opts)) != 4 or not all(o in blocks for o in opts) or not it.get("why"):
            err(f"pages/drill.yaml items[{i}]", "needs why, an answer and 3 distinct distractors, all block ids")
    terms = [t["term"] for t in pages["glossary"]["terms"]]
    for t in pages["glossary"]["terms"]:
        if t.get("see") not in blocks or not t.get("def"):
            err("pages/glossary.yaml", f"{t['term']}: needs def and a block id in see")
    for t in {t for t in terms if terms.count(t) > 1}:
        err("pages/glossary.yaml", f"duplicate term {t}")
    return pages


def version():
    """The guide's version, from VERSION (semver). Bump it when a changed build ships."""
    v = (ROOT / "VERSION").read_text().strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", v):
        sys.exit(f"VERSION must be MAJOR.MINOR.PATCH, got {v!r}")
    return v


def render(data, out):
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = (ROOT / "template.html").read_text().replace("/*__DATA__*/null", blob)
    html = html.replace("__VERSION__", version())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"→ {out} (v{version()}, {out.stat().st_size // 1024} KB)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default=str(ROOT / "dist" / "study-guide-sysd.html"))
    a = ap.parse_args()
    data = load()
    n_calc = sum(len(c.get("calc", [])) for b in data["blocks"] for c in b["checks"]) + \
        sum(len(s.get("calc", [])) for c in data["cases"] for s in c["steps"]) + \
        sum(len(pr["calc"]) for pr in data.get("pages", {}).get("est-drill", {}).get("problems", []))
    if errors:
        print("\n".join(errors))
        sys.exit(f"{len(errors)} problem(s) — HTML not written.")
    print(f"✓ {len(data['blocks'])} blocks, {len(data['cases'])} cases, {len(data['pages'])} site pages, {n_calc} estimates verified")
    render(data, pathlib.Path(a.out))


if __name__ == "__main__":
    main()
