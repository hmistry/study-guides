#!/usr/bin/env python3
"""Load guide.yaml + topics/*.yaml + pages/*.yaml, test every solution and every language-sheet example
(Python + Ruby), then render one offline HTML file.

usage: python3 build.py [-o OUT.html] [--skip-tests]
"""
import argparse, ast, contextlib, copy, io, json, pathlib, re, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
import yaml

ROOT = pathlib.Path(__file__).parent
PRISM = ["prism-core", "prism-clike", "prism-python", "prism-ruby"]
REQUIRED = ["id", "title", "difficulty", "statement", "example", "hint",
            "insight", "complexity", "fn", "tests", "solution"]

# Node classes the solutions may use, LeetCode-style (provided, not written by the solver).
# Shown on the page under "Node class" for problems whose tests use them.
NODES = {
    "list": {"python": """class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next
""", "ruby": """class ListNode
  attr_accessor :val, :next
  def initialize(val = 0, _next = nil)
    @val = val
    @next = _next
  end
end
"""},
    "tree": {"python": """class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right
""", "ruby": """class TreeNode
  attr_accessor :val, :left, :right
  def initialize(val = 0, left = nil, right = nil)
    @val = val
    @left = left
    @right = right
  end
end
"""},
}

# Test values: {list: [...], pos: i} → ListNode chain (tail → node i if pos given);
# {tree: [...]} → TreeNode from LeetCode level order (null = no child). Works nested in arrays.
# An `out` with the same tag reads the returned node back into that form for comparison.
PY_HARNESS = """
def _sg_list(vals, pos=-1):
    nodes = [ListNode(v) for v in vals]
    for a, b in zip(nodes, nodes[1:]):
        a.next = b
    if nodes and pos is not None and pos >= 0:
        nodes[-1].next = nodes[pos]
    return nodes[0] if nodes else None

def _sg_tree(vals):
    if not vals or vals[0] is None:
        return None
    root = TreeNode(vals[0])
    q, i = [root], 1
    for node in q:
        for side in ("left", "right"):
            if i < len(vals) and vals[i] is not None:
                setattr(node, side, TreeNode(vals[i]))
                q.append(getattr(node, side))
            i += 1
        if i >= len(vals):
            break
    return root

def _sg_decode(v):
    if isinstance(v, dict) and "list" in v:
        return _sg_list(v["list"], v.get("pos", -1))
    if isinstance(v, dict) and "tree" in v:
        return _sg_tree(v["tree"])
    if isinstance(v, list):
        return [_sg_decode(x) for x in v]
    return v

def _sg_encode(r, want):
    if isinstance(want, dict) and "list" in want:
        out, seen = [], set()
        while r is not None:
            if id(r) in seen:  # a buggy answer left a cycle: mark it instead of looping
                out.append("<cycle>")
                break
            seen.add(id(r))
            out.append(r.val)
            r = r.next
        return {"list": out}
    if isinstance(want, dict) and "tree" in want:
        out, q, seen = [], [r], set()
        for node in q:
            if node is not None and id(node) in seen:
                out.append("<cycle>")
                break
            out.append(None if node is None else node.val)
            if node is not None:
                seen.add(id(node))
                q += [node.left, node.right]
        while out and out[-1] is None:
            out.pop()
        return {"tree": out}
    if isinstance(want, list) and isinstance(r, list) and len(r) == len(want):
        return [_sg_encode(x, w) for x, w in zip(r, want)]
    return r

def _sg_call(fn, t):
    args = _sg_decode(t["args"])
    if "ops" not in t:
        return _sg_encode(fn(*args), t["out"])
    obj = globals()[t["ops"][0]](*args[0])
    outs = [None]
    for op, a, want in list(zip(t["ops"], args, t["out"]))[1:]:
        r = getattr(obj, op)(*a)
        outs.append(None if want is None else _sg_encode(r, want))
    return outs
"""

RUBY_HARNESS = """
def sg_list(vals, pos)
  nodes = vals.map { |v| ListNode.new(v) }
  nodes.each_cons(2) { |a, b| a.next = b }
  nodes[-1].next = nodes[pos] if !nodes.empty? && pos && pos >= 0
  nodes.first
end

def sg_tree(vals)
  return nil if vals.empty? || vals[0].nil?
  root = TreeNode.new(vals[0])
  q, i = [root], 1
  q.each do |node|
    %i[left right].each do |side|
      if i < vals.length && !vals[i].nil?
        child = TreeNode.new(vals[i])
        node.send("#{side}=", child)
        q << child
      end
      i += 1
    end
    break if i >= vals.length
  end
  root
end

def sg_decode(v)
  return sg_list(v["list"], v["pos"]) if v.is_a?(Hash) && v.key?("list")
  return sg_tree(v["tree"]) if v.is_a?(Hash) && v.key?("tree")
  return v.map { |x| sg_decode(x) } if v.is_a?(Array)
  v
end

def sg_encode(r, want)
  if want.is_a?(Hash) && want.key?("list")
    out, seen = [], {}.compare_by_identity
    while r
      (out << "<cycle>"; break) if seen[r]
      seen[r] = true
      out << r.val
      r = r.next
    end
    return {"list" => out}
  end
  if want.is_a?(Hash) && want.key?("tree")
    out, q, seen = [], [r], {}.compare_by_identity
    q.each do |node|
      (out << "<cycle>"; break) if node && seen[node]
      out << node&.val
      next unless node
      seen[node] = true
      q.push(node.left, node.right)
    end
    out.pop while !out.empty? && out[-1].nil?
    return {"tree" => out}
  end
  return r.zip(want).map { |x, w| sg_encode(x, w) } if want.is_a?(Array) && r.is_a?(Array) && r.length == want.length
  r
end

def sg_call(fn, t)
  args = sg_decode(t["args"])
  return sg_encode(send(fn, *args), t["out"]) unless t["ops"]
  obj = Object.const_get(t["ops"][0]).new(*args[0])
  outs = t["ops"].each_with_index.drop(1).map do |op, i|
    r = obj.send(op, *args[i])
    t["out"][i].nil? ? nil : sg_encode(r, t["out"][i])
  end
  [nil] + outs
end
"""

RUBY_RUNNER = """
require 'json'
%s
%s
%s
fn, tests = JSON.parse(STDIN.read)
out = tests.map do |t|
  begin
    {"ok" => sg_call(fn, t)}
  rescue => e
    {"err" => "#{e.class}: #{e.message}"}
  end
end
puts JSON.generate(out)
"""


def norm(v, mode, ops=False):
    if ops:  # op sequence: normalize each call's result on its own
        return [norm(x, mode) if isinstance(x, list) else x for x in v]
    if mode == "unordered":
        return sorted(sorted(x) if isinstance(x, list) else x for x in v)
    return v


def run_python(p, helper):
    ns = {}
    exec("".join(n["python"] for n in NODES.values()) + PY_HARNESS, ns)
    exec(helper.get("python", "") + "\n" + p["solution"]["python"], ns)
    fn = ns[p["fn"]]
    res = []
    for t in p["tests"]:
        try:
            res.append({"ok": ns["_sg_call"](fn, copy.deepcopy(t))})
        except Exception as e:  # report, don't crash the build
            res.append({"err": f"{type(e).__name__}: {e}"})
    return res


def run_ruby(p, helper):
    with tempfile.NamedTemporaryFile("w", suffix=".rb", delete=False) as f:
        nodes = "".join(n["ruby"] for n in NODES.values())
        f.write(RUBY_RUNNER % (nodes, RUBY_HARNESS, helper.get("ruby", "") + "\n" + p["solution"]["ruby"]))
    r = subprocess.run(["ruby", f.name], input=json.dumps([p["fn"], p["tests"]]),
                       capture_output=True, text=True, timeout=20)
    if r.returncode:
        return [{"err": r.stderr.strip()}] * len(p["tests"])
    return json.loads(r.stdout)


def test_all(data):
    failures = 0
    for pat in data["patterns"]:
        for p in pat["problems"]:
            missing = [k for k in REQUIRED if k not in p]
            if missing:
                print(f"✗ {p.get('id')}: missing {missing}")
                failures += 1
                continue
            uneven = [t for t in p["tests"] if "ops" in t
                      and not len(t["ops"]) == len(t["args"]) == len(t["out"])]
            if uneven:
                print(f"✗ {p['id']}: ops / args / out lengths differ in {len(uneven)} test(s)")
                failures += 1
                continue
            mode = p.get("compare", "exact")
            for lang, runner in (("python", run_python), ("ruby", run_ruby)):
                results = runner(p, pat.get("helper") or {})
                bad = []
                for t, r in zip(p["tests"], results):
                    ops = "ops" in t
                    if "err" in r or norm(r["ok"], mode, ops) != norm(t["out"], mode, ops):
                        bad.append(((f"ops={t['ops']} " if ops else "") + f"args={t['args']}", t["out"], r))
                status = "✓" if not bad else "✗"
                print(f"{status} {pat['id']}/{p['id']} [{lang}] {len(p['tests']) - len(bad)}/{len(p['tests'])}")
                for args, want, got in bad:
                    print(f"    {args} want={want} got={got}")
                failures += bool(bad)
    return failures


def check_refs(data):
    """Every pattern / drill / decision reference must point at a catalog id; page ids must be unique."""
    ids = {c["id"] for c in data["catalog"]}
    refs = [("pattern", p["id"]) for p in data["patterns"]]
    refs += [("drill", x) for it in data["drill"] for x in [it["answer"], *it["distractors"]]]
    refs += [("decision", o["go"]) for q in data["decision"] for o in q["opts"]]
    bad = [r for r in refs if r[1] not in ids]
    for kind, ref in bad:
        print(f"✗ unknown {kind} ref: {ref}")
    # pattern and problem ids become HTML ids and storage keys, so all must be unique
    page_ids = [p["id"] for p in data["patterns"]] + [q["id"] for p in data["patterns"] for q in p["problems"]]
    dupes = sorted({i for i in page_ids if page_ids.count(i) > 1})
    for i in dupes:
        print(f"✗ duplicate id: {i}")
    return len(bad) + len(dupes)


def node_kinds(v):
    """Node tags ({list: …} / {tree: …}) used anywhere in a test value."""
    if isinstance(v, dict):
        return {k for k in NODES if k in v} | {x for w in v.values() for x in node_kinds(w)}
    if isinstance(v, list):
        return {x for w in v for x in node_kinds(w)}
    return set()


# ── Language cheat sheet: each row's code runs in its language; the result must match `*_out`
# (repr / inspect of the last expression) or `*_stdout` (what it printed). `run: false` = syntax check only;
# `shell: true` = terminal commands, displayed with a `$` prompt and never run.
ROW_KEYS = {"task", "py", "rb", "py_out", "rb_out", "py_stdout", "rb_stdout",
            "note", "py_note", "rb_note", "trap", "since", "run", "shell"}
LANGS = {"py": "python", "rb": "ruby"}

RUBY_ROW = """
require 'json'
require 'stringio'
src = JSON.parse(STDIN.read)
real = $stdout
$stdout = StringIO.new
begin
  v = TOPLEVEL_BINDING.eval(src, "row")
  printed = $stdout.string
  $stdout = real
  puts JSON.generate({"value" => v.inspect, "stdout" => printed})
rescue Exception => e
  $stdout = real
  puts JSON.generate({"err" => "#{e.class}: #{e.message}"})
end
"""


def run_py_row(code, check):
    """→ {"value": repr(last expression), "stdout": printed} or {"err": …}."""
    try:
        if not check:
            compile(code, "row", "exec")
            return {}
        tree = ast.parse(code)
        last = tree.body.pop() if tree.body and isinstance(tree.body[-1], ast.Expr) else None
        ns, buf = {"__name__": "row"}, io.StringIO()
        with contextlib.redirect_stdout(buf):
            exec(compile(tree, "row", "exec"), ns)
            v = eval(compile(ast.Expression(last.value), "row", "eval"), ns) if last else None
        return {"value": repr(v), "stdout": buf.getvalue()}
    except BaseException as e:      # SystemExit included: a row must never stop the build
        return {"err": f"{type(e).__name__}: {e}"}


def run_rb_row(code, check):
    if not check:
        r = subprocess.run(["ruby", "-c", "-e", code], capture_output=True, text=True, timeout=20)
        return {} if r.returncode == 0 else {"err": r.stderr.strip()}
    r = subprocess.run(["ruby", "-e", RUBY_ROW], input=json.dumps(code), capture_output=True, text=True, timeout=20)
    if r.returncode:
        return {"err": r.stderr.strip()}
    return json.loads(r.stdout.strip().splitlines()[-1])


def check_langsheet(sheet):
    jobs = []
    for sec in sheet["sections"]:
        for row in sec["rows"]:
            bad = set(row) - ROW_KEYS
            if bad or "task" not in row or not ({"py", "rb"} & set(row)):
                print(f"✗ langsheet/{sec['id']}: bad row {row.get('task')!r} (unknown keys {sorted(bad)} or no code)")
                return 1
            if row.get("shell"):          # terminal commands: shown, never run
                continue
            for lg in LANGS:
                if lg in row:
                    given = (sec.get("given") or {}).get(lg, "")
                    jobs.append((sec["id"], row, lg, (given + "\n" if given else "") + row[lg]))
    run = lambda j: (j, (run_py_row if j[2] == "py" else run_rb_row)(j[3], j[1].get("run", True)))
    # Ruby rows are one process each, so they run in parallel. Python rows run here, one at a time:
    # they swap sys.stdout to capture prints, which must not race with other threads.
    with ThreadPoolExecutor(8) as pool:
        rb = pool.map(run, [j for j in jobs if j[2] == "rb"])
        results = [run(j) for j in jobs if j[2] == "py"] + list(rb)
    failures = 0
    for lg, name in LANGS.items():
        mine = [(j, r) for j, r in results if j[2] == lg]
        bad = []
        for (sid, row, _, _), r in mine:
            if "err" in r:
                bad.append((sid, row["task"], "error", r["err"]))
            elif f"{lg}_out" in row and r["value"] != row[f"{lg}_out"]:
                bad.append((sid, row["task"], row[f"{lg}_out"], r["value"]))
            elif f"{lg}_stdout" in row and r["stdout"].rstrip("\n") != row[f"{lg}_stdout"]:
                bad.append((sid, row["task"], row[f"{lg}_stdout"], r["stdout"]))
        print(f"{'✓' if not bad else '✗'} langsheet [{name}] {len(mine) - len(bad)}/{len(mine)}")
        for sid, task, want, got in bad:
            print(f"    {sid} / {task}: want {want!r} got {got!r}")
        failures += bool(bad)
    return failures


def page_data(data):
    """Tests stay in the page (shown as test cases). Each problem gets the node classes its tests use."""
    data = copy.deepcopy(data)
    data["nodes"] = NODES
    for pat in data["patterns"]:
        for p in pat["problems"]:
            p["nodes"] = sorted(node_kinds([[t["args"], t["out"]] for t in p["tests"]]))
    return data


def version():
    """The guide's version, from VERSION (semver). Bump it when a changed build ships."""
    v = (ROOT / "VERSION").read_text().strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", v):
        sys.exit(f"VERSION must be MAJOR.MINOR.PATCH, got {v!r}")
    return v


def render(data, out):
    prism = "\n".join((ROOT / "vendor" / f"{n}.min.js").read_text() for n in PRISM)
    blob = json.dumps(page_data(data), ensure_ascii=False).replace("</", "<\\/")
    html = (ROOT / "template.html").read_text()
    html = html.replace("/*__PRISM__*/", prism).replace("/*__DATA__*/null", blob)
    html = html.replace("__VERSION__", version())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"→ {out} (v{version()}, {out.stat().st_size // 1024} KB)")


def load():
    """guide.yaml (catalog order) + topics/<id>.yaml (one pattern each) + pages/*.yaml → one data dict."""
    read = lambda f: yaml.safe_load(f.read_text())
    catalog = read(ROOT / "guide.yaml")["catalog"]
    ids = [c["id"] for c in catalog]
    files = {f.stem: f for f in sorted((ROOT / "topics").glob("*.yaml"))}
    stray = sorted(set(files) - set(ids))
    if stray:
        sys.exit(f"topics/ files not in guide.yaml catalog: {stray}")
    patterns = [read(files[i]) for i in ids if i in files]
    for f, p in zip([files[i] for i in ids if i in files], patterns):
        if p.get("id") != f.stem:
            sys.exit(f"topics/{f.name}: id must be {f.stem!r}, got {p.get('id')!r}")
    pages = ROOT / "pages"
    return {"patterns": patterns, "catalog": catalog, "decision": read(pages / "decision.yaml")["decision"],
            "drill": read(pages / "drill.yaml")["drill"], "langsheet": read(pages / "langsheet.yaml")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default=str(ROOT / "dist" / "study-guide-algo.html"))
    ap.add_argument("--skip-tests", action="store_true")
    a = ap.parse_args()
    data = load()
    if check_refs(data):
        sys.exit("Bad references — HTML not written.")
    if not a.skip_tests and (test_all(data) + check_langsheet(data["langsheet"])):
        sys.exit("Tests failed — HTML not written.")
    render(data, pathlib.Path(a.out))


if __name__ == "__main__":
    main()
