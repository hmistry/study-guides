#!/usr/bin/env python3
"""Validate guide.yaml + topics/*.yaml, run every query against a throwaway Postgres, then render one offline HTML file.

usage: python3 build.py [-o OUT.html]

The build starts its own Postgres cluster (initdb + pg_ctl, Unix socket only, no TCP port) in a temp dir,
loads data/dataset.sql exactly as a reader would, and runs:
  - every problem solution, compared with its hand-written `expect` table (or its DDL `tests`),
  - every snippet (compared with `out` when given).
Each run is wrapped in BEGIN … ROLLBACK, so nothing leaks between problems. Any failure → no HTML.
"""
import argparse, csv, io, json, pathlib, re, shutil, subprocess, sys, tempfile
from decimal import Decimal, InvalidOperation
import yaml

ROOT = pathlib.Path(__file__).parent
PRISM = ["prism-core", "prism-sql"]
TOPIC_KEYS = {"id", "name", "signal", "idea", "diagram", "numbers", "tables", "snippets", "pitfalls", "depth", "mysql", "checks", "problems"}
REQUIRED = {"A": {"id", "name", "signal", "idea", "pitfalls", "problems"},
            "B": {"id", "name", "signal", "idea", "pitfalls", "depth", "checks"}}
PROBLEM_KEYS = {"id", "title", "variant", "statement", "hint", "setup", "solution", "check", "expect", "tests", "insight", "mysql", "uses_index"}
SNIPPET_KEYS = {"task", "sql", "out", "note", "mysql", "run", "since", "shell", "tx"}
TEST_KEYS = {"sql", "ok", "error", "uses_index", "note"}
# SQLSTATE condition names the content may expect (https://www.postgresql.org/docs/current/errcodes-appendix.html)
SQLSTATE = {"unique_violation": "23505", "foreign_key_violation": "23503", "not_null_violation": "23502",
            "check_violation": "23514", "generated_always": "428C9", "invalid_table_definition": "42P16", "exclusion_violation": "23P01", "serialization_failure": "40001",
            "deadlock_detected": "40P01", "lock_not_available": "55P03", "undefined_column": "42703",
            "undefined_table": "42P01", "invalid_text_representation": "22P02", "division_by_zero": "22012"}
SOLUTION_W = 58   # widest solution line that fits the revealed pane at 1280px without scrolling
NULL = "<NULL>"
DB = "practice"
errors = []


def err(where, msg):
    errors.append(f"✗ {where}: {msg}")


# ── a throwaway Postgres cluster
class Postgres:
    def __enter__(self):
        for tool in ("initdb", "pg_ctl", "psql"):
            if not shutil.which(tool):
                sys.exit(f"{tool} not found: install PostgreSQL (brew install postgresql@18)")
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix="sqpg.", dir="/tmp"))   # short path: Unix socket paths max ~100 chars
        data = self.dir / "data"
        subprocess.run(["initdb", "-D", data, "-U", "postgres", "--auth=trust", "-E", "UTF8", "--locale=C"],
                       check=True, capture_output=True)
        opts = f"-k {self.dir} -c listen_addresses='' -c timezone=UTC -c fsync=off -c synchronous_commit=off"
        subprocess.run(["pg_ctl", "-D", data, "-o", opts, "-w", "-l", self.dir / "log", "start"], check=True, capture_output=True)
        return self

    def __exit__(self, *exc):
        subprocess.run(["pg_ctl", "-D", self.dir / "data", "-m", "immediate", "stop"], capture_output=True)
        shutil.rmtree(self.dir, ignore_errors=True)

    def psql(self, script, db=DB):
        """Run a script; return (ok, stdout, error text)."""
        p = subprocess.run(["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "--csv", "-h", str(self.dir), "-U", "postgres",
                            "-d", db, "-f", "-"], input=f"\\pset null '{NULL}'\n{script}", text=True, capture_output=True)
        return p.returncode == 0, p.stdout, p.stderr.strip().replace("psql:<stdin>:", "line ")

    def rows(self, script, db=DB):
        ok, out, e = self.psql(script, db)
        if not ok:
            raise RuntimeError(e)
        table = list(csv.reader(io.StringIO(out)))
        return (table[0], table[1:]) if table else ([], [])


# ── result comparison: hand-written YAML values vs psql CSV text
def cell(v):
    """YAML value → the text psql prints (dates come out of YAML as date objects; str() gives ISO)."""
    if v is None:
        return NULL
    if isinstance(v, bool):
        return "t" if v else "f"
    return str(v)


def canon(s):
    """'190000.00' and '190000' compare equal; everything else compares as text."""
    try:
        d = Decimal(s)
        return format(d.normalize(), "f") if d == d.to_integral() else str(d.normalize())
    except InvalidOperation:
        return s


def compare(where, expect, cols, rows):
    want_cols = [str(c) for c in expect["cols"]]
    if cols != want_cols:
        err(where, f"columns {cols} ≠ expected {want_cols}")
        return
    want = [[canon(cell(v)) for v in r] for r in expect["rows"]]
    got = [[canon(v) for v in r] for r in rows]
    if expect.get("order", True) is False:
        want, got = sorted(want), sorted(got)
    if want != got:
        diff = next((i for i, (a, b) in enumerate(zip(want, got)) if a != b), min(len(want), len(got)))
        err(where, f"result differs ({len(got)} rows, expected {len(want)}); first difference at row {diff + 1}: "
                   f"got {got[diff] if diff < len(got) else '—'}, expected {want[diff] if diff < len(want) else '—'}")


# Sequences aren't transactional: a rolled-back INSERT still consumes ids. Every run starts by resetting each
# identity sequence to max(id), so results never depend on which problems ran before.
RESET = """DO $reset$ DECLARE r record; BEGIN
  FOR r IN SELECT c.relname AS tbl, a.attname AS col, pg_get_serial_sequence(c.relname, a.attname) AS seq
           FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'public' AND a.attidentity <> '' LOOP
    EXECUTE format('SELECT setval(%L, coalesce((SELECT max(%I) FROM %I), 0) + 1, false)', r.seq, r.col, r.tbl);
  END LOOP; END $reset$;"""


def stmt(sql):
    sql = sql.rstrip()
    return sql if sql.endswith(";") else sql + ";"


def plan_check(i, sql, want):
    """A DO block that EXPLAINs `sql` with seq scans disabled and records whether the plan uses an index
    (want=True) or the named index (want="name")."""
    pat = "Index" if want is True else want
    return f"""DO $do$ DECLARE r record; plan text := ''; BEGIN
  SET LOCAL enable_seqscan = off;
  FOR r IN EXECUTE 'EXPLAIN ' || {dollar(sql)} LOOP plan := plan || r."QUERY PLAN" || ' / '; END LOOP;
  SET LOCAL enable_seqscan = on;
  INSERT INTO _t VALUES ({i}, CASE WHEN position({pat!r} in plan) > 0 THEN 'index' ELSE 'no index: ' || plan END);
EXCEPTION WHEN OTHERS THEN INSERT INTO _t VALUES ({i}, 'error ' || SQLSTATE || ' ' || SQLERRM); END $do$;"""


def index_msg(want):
    return "an index to be usable" if want is True else f"the plan to use {want}"


def run_query_problem(pg, where, p):
    """setup (+ solution when a `check` query reads the result) run silently; the last query's output is compared.
    With `uses_index`, the solution's plan must also use an index (or the named one) when seq scans are off."""
    quiet = stmt(p["setup"]) if p.get("setup") else ""
    if p.get("check"):
        quiet += "\n" + stmt(p["solution"])
    last = stmt(p["check"] if p.get("check") else p["solution"])
    try:
        cols, rows = pg.rows(f"BEGIN;\n\\o /dev/null\n{RESET}\n{quiet}\n\\o\n{last}\nROLLBACK;\n")
    except RuntimeError as e:
        return err(where, f"solution failed: {e}")
    compare(where, p["expect"], cols, rows)
    if p.get("uses_index"):
        setup = stmt(p["setup"]) if p.get("setup") else ""
        script = (f"BEGIN;\n\\o /dev/null\n{RESET}\n{setup}\nCREATE TEMP TABLE _t (i int, res text);\n"
                  f"{plan_check(0, p['solution'], p['uses_index'])}\n\\o\nSELECT res FROM _t;\nROLLBACK;\n")
        try:
            _, [[res]] = pg.rows(script)
        except (RuntimeError, ValueError) as e:
            return err(where, f"plan check failed: {e}")
        if res != "index":
            err(where, f"expected {index_msg(p['uses_index'])}, got: {res}")


def dollar(sql):
    if "$t$" in sql:
        raise ValueError("test SQL may not contain $t$")
    return f"$t${sql.rstrip().rstrip(';')}$t$"


SPLIT = "@@SPLIT@@"


def run_ddl_problem(pg, where, p):
    """Run setup + solution, then each test in its own sub-transaction (a DO block that records its outcome).
    Effects of passing tests are kept, in order. An optional `check` query then reads the final state."""
    body = []
    for i, t in enumerate(p["tests"]):
        if t.get("uses_index"):
            body.append(plan_check(i, t["sql"], t["uses_index"]))
        else:
            body.append(f"""DO $do$ BEGIN EXECUTE {dollar(t["sql"])}; INSERT INTO _t VALUES ({i}, 'ok');
EXCEPTION WHEN OTHERS THEN INSERT INTO _t VALUES ({i}, 'error ' || SQLSTATE || ' ' || SQLERRM); END $do$;""")
    check = f"\\echo {SPLIT}\n{stmt(p['check'])}\n" if p.get("check") else ""
    script = (f"BEGIN;\n\\o /dev/null\n{RESET}\n{stmt(p['setup']) if p.get('setup') else ''}\n{stmt(p['solution'])}\n"
              f"CREATE TEMP TABLE _t (i int, res text);\n" + "\n".join(body) +
              f"\n\\o\nSELECT res FROM _t ORDER BY i;\n{check}ROLLBACK;\n")
    ok, out, e = pg.psql(script)
    if not ok:
        return err(where, f"solution failed: {e}")
    parts = out.split(SPLIT + "\n")
    rows = list(csv.reader(io.StringIO(parts[0])))[1:]
    for i, (t, (res,)) in enumerate(zip(p["tests"], rows)):
        tw = f"{where} tests[{i}]"
        if t.get("uses_index"):
            if res != "index":
                err(tw, f"expected {index_msg(t['uses_index'])}, got: {res}")
        elif t.get("error"):
            code = SQLSTATE[t["error"]]
            if not res.startswith(f"error {code}"):
                err(tw, f"expected {t['error']} ({code}), got: {res}")
        elif res != "ok":
            err(tw, f"expected success, got: {res}")
    if p.get("check"):
        table = list(csv.reader(io.StringIO(parts[1])))
        compare(f"{where} check", p["expect"], table[0], table[1:])


def run_snippet(pg, where, s):
    """In a rolled-back transaction, or (tx: false: CREATE DATABASE, VACUUM, CONCURRENTLY) in a throwaway clone."""
    if s.get("run") is False or s.get("shell"):
        return
    db = DB
    if s.get("tx") is False:
        db = "scratch"
        pg.psql(f"DROP DATABASE IF EXISTS scratch; CREATE DATABASE scratch TEMPLATE {DB};", db="postgres")
        wrap = lambda sql: f"{stmt(sql)}\n"
    else:
        wrap = lambda sql: f"BEGIN;\n\\o /dev/null\n{RESET}\n\\o\n{stmt(sql)}\nROLLBACK;\n"
    try:
        if "out" in s:
            cols, rows = pg.rows(wrap(s["sql"]), db)
            compare(where, s["out"], cols, rows)
        else:
            ok, _, e = pg.psql(f"\\o /dev/null\n{wrap(s['sql'])}", db)
            if not ok:
                err(where, e)
    except RuntimeError as e:
        err(where, str(e))
    if db == "scratch":
        pg.psql("DROP DATABASE scratch WITH (FORCE);", db="postgres")


# ── content checks
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
    t = d.get("type")
    if t not in ("timeline", "plan", "table"):
        return err(where, f"diagram type {t!r} (timeline | plan | table)")
    if not d.get("frames"):
        return err(where, "diagram has no frames")
    for i, f in enumerate(d["frames"]):
        fw = f"{where} frame {i}"
        if "title" not in f:
            err(fw, "needs a title")
        if t == "timeline":
            for s in f.get("steps", []):
                if s.get("t") not in f.get("sessions", d.get("sessions", [])):
                    err(fw, f"step session {s.get('t')!r} not in sessions {f.get('sessions', d.get('sessions'))}")
                if s.get("mark") not in (None, "ok", "bad", "wait", "error", "sees"):
                    err(fw, f"step mark {s.get('mark')!r}")
        elif t == "plan":
            depth = -1
            for n in f.get("plan", []):
                if "op" not in n:
                    err(fw, "plan node needs op")
                if n.get("d", 0) > depth + 1:
                    err(fw, f"plan node {n.get('op')} skips a level")
                depth = n.get("d", 0)
        else:
            n = len(d.get("rows", []))
            for k in [f.get("cur")] + list(f.get("win", [])):
                if k is not None and not 0 <= k < n:
                    err(fw, f"row index {k} out of range")
            if any(len(r) != len(d.get("cols", [])) for r in d.get("rows", [])):
                err(where, "table rows must match cols")


def check_topic(t, file, part, ids):
    where = f"topics/{file.name}"
    if t.get("id") != file.stem:
        err(where, f"id {t.get('id')!r} must match the file name")
    if bad := set(t) - TOPIC_KEYS:
        err(where, f"unknown keys {sorted(bad)}")
    if missing := REQUIRED[part] - set(t):
        return err(where, f"missing {sorted(missing)}")
    n = len(t.get("problems", []))
    if part == "A" and n != 2:
        err(where, f"Part A topics have exactly 2 problems (has {n})")
    if part == "B" and n > 2:
        err(where, f"Part B topics have at most 2 problems (has {n})")
    if t.get("diagram"):
        check_diagram(where, t["diagram"])
    for tb in t.get("tables", []):
        if any(len(r) != len(tb["cols"]) for r in tb["rows"]):
            err(where, f"table {tb['title']!r}: rows don't match cols")
    for i, s in enumerate(t.get("snippets", [])):
        if bad := set(s) - SNIPPET_KEYS:
            err(f"{where} snippets[{i}]", f"unknown keys {sorted(bad)}")
        if not {"task", "sql"} <= set(s):
            err(f"{where} snippets[{i}]", "needs task and sql")
    for i, c in enumerate(t.get("checks", [])):
        if not {"q", "a"} <= set(c):
            err(f"{where} checks[{i}]", "needs q and a")
        check_md(f"{where} checks[{i}]", c.get("a"))
    for p in t.get("problems", []):
        pw = f"{where} {p.get('id')}"
        ids.append(p.get("id"))
        if bad := set(p) - PROBLEM_KEYS:
            err(pw, f"unknown keys {sorted(bad)}")
        if missing := {"id", "title", "variant", "statement", "hint", "solution", "insight"} - set(p):
            err(pw, f"missing {sorted(missing)}")
        if long := [l for l in str(p.get("solution", "")).split("\n") if len(l) > SOLUTION_W]:
            err(pw, f"solution line over {SOLUTION_W} chars (it would scroll in the side-by-side pane): {long[0].strip()[:40]}…")
        if p.get("variant") not in ("canonical", "disguise"):
            err(pw, "variant must be canonical or disguise")
        if "expect" not in p and "tests" not in p:
            err(pw, "needs expect (a query problem) or tests (a DDL problem)")
        if "tests" in p and "expect" in p and "check" not in p:
            err(pw, "a DDL problem with expect needs a check query to produce it")
        if "tests" in p and p.get("uses_index"):
            err(pw, "uses_index on a DDL problem goes on a test, not the problem")
        if "expect" in p and any(len(r) != len(p["expect"]["cols"]) for r in p["expect"]["rows"]):
            err(pw, "expect rows must match cols")
        for i, ts in enumerate(p.get("tests", [])):
            if bad := set(ts) - TEST_KEYS:
                err(f"{pw} tests[{i}]", f"unknown keys {sorted(bad)}")
            if sum(k in ts for k in ("ok", "error", "uses_index")) != 1:
                err(f"{pw} tests[{i}]", "needs exactly one of ok / error / uses_index")
            if ts.get("error") and ts["error"] not in SQLSTATE:
                err(f"{pw} tests[{i}]", f"unknown error {ts['error']!r}; add it to SQLSTATE in build.py")


def load():
    guide = yaml.safe_load((ROOT / "guide.yaml").read_text())
    data = {"catalog": guide, "topics": []}
    cat = [(e["id"], part) for part, key in (("A", "partA"), ("B", "partB")) for e in guide[key]]
    if len({c for c, _ in cat}) != len(cat):
        err("guide.yaml", "duplicate topic ids")
    files = {f.stem: f for f in sorted((ROOT / "topics").glob("*.yaml"))}
    for stem in files.keys() - {c for c, _ in cat}:
        err(f"topics/{stem}.yaml", "not in guide.yaml catalog")
    ids = []
    for cid, part in cat:                                   # catalog order = page order
        if cid not in files:
            continue
        try:
            t = yaml.safe_load(files[cid].read_text())
        except yaml.YAMLError as e:
            err(f"topics/{cid}.yaml", f"YAML: {e}".replace("\n", " "))
            continue
        check_topic(t, files[cid], part, ids)
        t["part"] = part
        data["topics"].append(t)
    ids += [t["id"] for t in data["topics"]]                 # topic + problem ids share the HTML id space
    for i in {i for i in ids if ids.count(i) > 1}:
        err("ids", f"duplicate id {i}")
    data["pages"] = load_pages(data)
    return data


SITE_PAGES = ("cheat", "drill", "glossary")


def load_pages(data):
    """pages/<name>.yaml; every topic reference must be a catalog id (the cheat sheet covers every written topic, in order)."""
    pages = {}
    for name in SITE_PAGES:
        try:
            pages[name] = yaml.safe_load((ROOT / "pages" / f"{name}.yaml").read_text())
        except (OSError, yaml.YAMLError) as e:
            err(f"pages/{name}.yaml", str(e).replace("\n", " "))
            return {}
    cat = [e["id"] for k in ("partA", "partB") for e in data["catalog"][k]]
    written = [t["id"] for t in data["topics"]]
    rows = pages["cheat"].get("topics", [])
    if [r.get("id") for r in rows] != written:
        err("pages/cheat.yaml", f"topics rows must list every written topic once, in catalog order: {written}")
    for r in rows:
        if set(r) != {"id", "when", "move", "gotcha"}:
            err("pages/cheat.yaml", f"row {r.get('id')}: keys must be id, when, move, gotcha")
    for g in pages["cheat"].get("syntax", []):
        for r in g.get("rows", []):
            if set(r) - {"task", "sql", "run"} or not {"task", "sql"} <= set(r):
                err("pages/cheat.yaml", f"syntax row {r.get('task')!r}: keys are task, sql, run")
    for i, it in enumerate(pages["drill"].get("items", [])):
        opts = [it.get("answer")] + list(it.get("distractors", []))
        if len(opts) != 4 or len(set(opts)) != 4 or not all(o in cat for o in opts) or not it.get("why") or not it.get("prompt"):
            err(f"pages/drill.yaml items[{i}]", "needs prompt, why, an answer and 3 distinct distractors, all topic ids")
    terms = [t.get("term") for t in pages["glossary"].get("terms", [])]
    for t in pages["glossary"].get("terms", []):
        if t.get("see") not in cat or not t.get("def"):
            err("pages/glossary.yaml", f"{t.get('term')}: needs def and a topic id in see")
    for t in {t for t in terms if terms.count(t) > 1}:
        err("pages/glossary.yaml", f"duplicate term {t}")
    return pages


def dataset_info(pg):
    """Every table's columns, constraints and rows, straight from the loaded database (so the page can't drift)."""
    _, tables = pg.rows("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                        "WHERE n.nspname = 'public' AND c.relkind = 'r' ORDER BY c.oid;")
    out = []
    for (name,) in tables:
        _, cols = pg.rows(f"SELECT a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull FROM pg_attribute a "
                          f"WHERE a.attrelid = '{name}'::regclass AND a.attnum > 0 AND NOT a.attisdropped ORDER BY a.attnum;")
        _, cons = pg.rows(f"SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = '{name}'::regclass "
                          f"AND contype IN ('p', 'u', 'f', 'c') ORDER BY contype DESC, conname;")
        head, rows = pg.rows(f"SELECT * FROM {name} ORDER BY 1, 2;")
        out.append({"name": name, "columns": [{"name": c, "type": ty, "notnull": nn == "t"} for c, ty, nn in cols],
                    "constraints": [c for (c,) in cons], "cols": head,
                    "rows": [[None if v == NULL else v for v in r] for r in rows]})
    return out


def run_all(data):
    with Postgres() as pg:
        ok, _, e = pg.psql((ROOT / "data" / "dataset.sql").read_text(), db="postgres")
        if not ok:
            err("data/dataset.sql", e)
            return 0
        data["dataset"] = {"script": (ROOT / "data" / "dataset.sql").read_text(), "tables": dataset_info(pg)}
        n = 0
        for g in data["pages"]["cheat"].get("syntax", []):
            for r in g["rows"]:
                if r.get("run") is not False:
                    run_snippet(pg, f"pages/cheat.yaml syntax ({r['task']})", r); n += 1
        for t in data["topics"]:
            for i, s in enumerate(t.get("snippets", [])):
                run_snippet(pg, f"topics/{t['id']}.yaml snippets[{i}] ({s.get('task')})", s)
                n += s.get("run") is not False and not s.get("shell")
            for p in t.get("problems", []):
                w = f"topics/{t['id']}.yaml {p['id']}"
                run_ddl_problem(pg, w, p) if "tests" in p else run_query_problem(pg, w, p)
                n += 1
        return n


def version():
    """The guide's version, from VERSION (semver). Bump it when a changed build ships."""
    v = (ROOT / "VERSION").read_text().strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", v):
        sys.exit(f"VERSION must be MAJOR.MINOR.PATCH, got {v!r}")
    return v


def render(data, out):
    blob = json.dumps(data, ensure_ascii=False, default=str).replace("</", "<\\/")
    prism = "\n".join((ROOT / "vendor" / f"{n}.min.js").read_text() for n in PRISM)
    html = (ROOT / "template.html").read_text().replace("/*__PRISM__*/", prism).replace("/*__DATA__*/null", blob)
    html = html.replace("__VERSION__", version())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"→ {out} (v{version()}, {out.stat().st_size // 1024} KB)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default=str(ROOT / "dist" / "study-guide-sqldb.html"))
    a = ap.parse_args()
    data = load()
    n = 0 if errors else run_all(data)
    if errors:
        print("\n".join(errors))
        sys.exit(f"{len(errors)} problem(s) — HTML not written.")
    probs = sum(len(t.get("problems", [])) for t in data["topics"])
    print(f"✓ {len(data['topics'])} topics, {probs} problems; {n} solutions and snippets ran and matched; "
          f"dataset: {len(data['dataset']['tables'])} tables")
    render(data, pathlib.Path(a.out))


if __name__ == "__main__":
    main()
