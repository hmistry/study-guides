# Algorithm Patterns Study Guide — Plan

A single offline HTML page for **fast review** of common interview algorithm patterns, in **Python and Ruby**. You write an attempt in a scratch editor, then reveal a verified solution beside it. This is quick review before interviews, not first-time learning material: keep the text terse but beyond basics.

## Status (2026-10-09)

- **Done:** all 16 patterns, 2 problems each. All 32 solutions pass in both languages. #6–16 were written in one go at the user's request and are awaiting review.
- **Harness:** linked-list / binary-tree test values and class-design (op-sequence) tests done (work order steps 1–2).
- **Diagram types done:** `array` (default), `linked`, `intervals`, `grid`, `tree`, `graph`.
- **Site-wide features done:** Home, Decision Guide, Cheat Sheet (all 16 patterns), Pattern Drill (16 questions), Language Cheat Sheet (Python + Ruby, 16 sections), progress tracking, backup and reset.
- **Next:** see [Work order](#work-order).

## Files

| File | Role |
|---|---|
| `guide.yaml` | **Catalog**: all 16 patterns in display order (cheat-sheet rows + numbering). A `topics/` file must have an entry here. |
| `topics/<id>.yaml` | **One pattern per file** (template, problems, solutions, tests). Edit these, not the HTML. |
| `pages/decision.yaml`, `pages/drill.yaml` | Decision guide and Pattern Drill. Every `go` / answer / distractor is a catalog id. |
| `pages/langsheet.yaml` | **Language Cheat Sheet** rows. Every row runs in its language during the build. Schema is in the file header. |
| `build.py` | Validates references, tests every solution in Python + Ruby, then renders `dist/study-guide-algo.html`. Refuses to write HTML if anything fails. |
| `template.html` | Page shell: CSS + vanilla JS renderer. Data and Prism are inlined at build time. |
| `vendor/` | Prism 1.29 (core, clike, python, ruby), inlined so the page works offline. |
| `tests/ui_check.py` | Headless-browser checks: reveal hidden-first, test cases, filters, export/import round trip, drill, mobile overflow, JS errors. |
| `dist/study-guide-algo.html` | **Build output.** Never hand-edit. |
| `VERSION` | Guide version (semver), shown in the page. |
| `file-mods.log` | Change log (see Working rules). |

```bash
pip install pyyaml playwright && playwright install chromium   # ruby ≥ 3.0 also required
python3 build.py              # test + build → dist/study-guide-algo.html
python3 build.py --skip-tests # layout iteration only; never ship this way
python3 tests/ui_check.py     # after every template change
```

## Content rules (per pattern)

| Field | Rule |
|---|---|
| `signal` | 3–5 short phrases that show up in problem statements. |
| `idea` | Core Idea, **2–3 lines**: the mechanism, when each variant applies, the complexity payoff. |
| `diagram` | One per pattern, not per problem. It shows the mechanic, not a specific problem. |
| `template` | Generic skeleton in both languages, using placeholder helpers (`found`, `keep`, `invalid`). |
| `pitfalls` | **3–5 items**, beyond basics: off-by-ones, when the pattern breaks, generalizations, tricks. |
| `problems` | **Exactly 2.** (1) *canonical*, where the pattern is obvious and teaches the template; (2) *variant / disguise*, where the pattern is less obvious. This trains recognition. Difficulty is a tag, not the selection axis. |

Per problem:
- **Fields:** `title`, `difficulty`, `variant`, `statement`, `example`, `hint` (a nudge, not the answer), `insight` (shown after reveal), `complexity`.
- **Tests:** `fn` plus `tests` (4–6, each with a `note` naming the edge case it covers), and optional `compare: unordered`.
- **Node values:** `{list: [3,2,0,-4], pos: 1}` becomes a `ListNode` chain, and `pos` (optional) links the tail back to that index. `{tree: [3,9,20,null,null,15,7]}` becomes a `TreeNode`, using LeetCode level order. Both work nested, e.g. `args: [[{list: [1,4]}, {list: [2]}]]`. Put the same tag in `out` when the function returns a node. The harness reads the returned node back into that form and marks a cycle as `"<cycle>"`. The classes are defined in `build.py` (`NODES`), so solutions don't define them. The page shows them under "Provided" on any problem whose tests use them.
- **Pattern helper:** optional `helper: {python, ruby}` on a pattern. It is prepended to that pattern's solutions when testing, shown under "Provided", and included in that language's solution Export. Used for the Ruby `MinHeap` (#9); its Python side is just a comment, since `heapq` is built in.
- **Class-design tests** (LeetCode style): `fn` is the class name, and each test is `{ops: [Trie, insert, search], args: [[], ["apple"], ["apple"]], out: [null, null, true]}`. `ops[0]` constructs with `args[0]`, and the rest are called in order on that instance. A `null` in `out` means that call isn't checked (void methods; Ruby returns its last expression). The three lists must be the same length or the build fails. Method names are snake_case and identical in both languages (`starts_with`, not `startsWith`). `compare: unordered` applies to each call's result separately.
- **Solutions:** `solution.python` and `solution.ruby`. Same function name in both. Comments only where the line isn't self-evident.
- **Text:** inline `` `code` `` renders as code. Quote YAML strings that start with `"` or contain `: `.

When a pattern section is written, its entry in `catalog` (cheat-sheet row) must still agree with it. The two are kept in sync by hand.

## Language Cheat Sheet (Reference)

An everyday Python / Ruby syntax reference, not limited to what the patterns need (user decision, 2026-10-09). It's one page that follows the global language toggle, with section chips, a live filter box and a Print button.

- **Row format:** task → code (one line or a short block) → result (`*_out` = repr / inspect of the last expression, or `*_stdout` = printed output), plus optional notes, `trap` (⚠), `since` (version tag), and `run: false` (syntax-check only).
- **Spacing (user, 2026-10-09):** roomy rows (18px padding) with a 10px gap between code, result and note.
- **Layout convention (user, 2026-10-09):** every code sample is full width, even one-liners, and the result always sits on its own line below the code, never beside it. Notes go below that. This keeps rows easy to scan. `ui_check.py` guards it.
- **Notes stay in their language:** a note that names one language's feature goes in `py_note` / `rb_note`, not the shared `note`.
- **Language-specific rows:** a row may exist in only one language, e.g. Ruby `case/when` or the Python mutable-default trap.
- **Tested:** `build.py` runs every row. Python runs in-process with a fresh namespace per row; Ruby runs one process per row, 8 at a time. A wrong result, an exception or an unknown key fails the build.
- **Version targets:** Python 3.11+, Ruby 3.2+. Expected Ruby output uses 3.4+ `inspect` (`{"a" => 1}`).
- **Python vs Ruby traps:** all 14 were folded into the sections as ⚠ rows, and the separate Python vs Ruby page and its `langnotes` data were removed (batch 3).

| # | Section | Batch |
|---|---|---|
| 1 | Basics | 1 ✅ |
| 2 | Control flow | 1 ✅ |
| 3 | Functions & blocks | 1 ✅ |
| 4 | Strings | 1 ✅ |
| 5 | Lists / Arrays | 2 ✅ |
| 6 | Dicts / Hashes & Sets | 2 ✅ |
| 7 | Records (tuple, namedtuple, dataclass, Struct, Data) | 2 ✅ |
| 8 | Classes & objects | 2 ✅ |
| 9 | Imports & project setup: imports / require, `__main__`, stdlib, **venv, uv, pip; rbenv / chruby, Bundler / Gemfile, gem** | 2 ✅ |
| 10 | Errors | 2 ✅ |
| 11 | Iteration helpers | 3 ✅ |
| 12 | Stack, queue, heap | 3 ✅ |
| 13 | Recursion & memo | 3 ✅ |
| 14 | Grid & graph idioms | 3 ✅ |
| 15 | Bits | 3 ✅ |
| 16 | I/O & everyday stdlib (stdin, files, JSON, dates, random, argv, env) | 3 ✅ |

All 16 sections are done: 214 Python rows and 221 Ruby rows (210 / 217 run in the build; the rest are shell rows).
- **Shell rows** (`shell: true`) hold terminal commands (venv, uv, pip, rbenv / chruby, Bundler, gem). They're shown with a `$` prompt, dimmed `# comments` and a "shell" tag, and never run. Non-runnable Ruby/Python files (a Gemfile, relative imports) use `run: false`, which is syntax-checked only.
- **Runner detail:** Python rows run on the main thread, one at a time. They swap `sys.stdout` to capture prints, and doing that from worker threads once swallowed the build's own output. Only Ruby rows (one process each) run in the thread pool.

## The 16 patterns and problem pairs (approved)

| # | id | Canonical | Variant / disguise | Status |
|---|---|---|---|---|
| 1 | two-pointers | Two Sum II (E) | 3Sum (M) | ✅ |
| 2 | sliding-window | Max Sum Subarray of K (E) | Longest Substring w/o Repeats (M) | ✅ |
| 3 | fast-slow | Linked List Cycle (E) | Find the Duplicate Number (M): array as linked list | ✅ |
| 4 | merge-intervals | Merge Intervals (M) | Meeting Rooms II (M)* | ✅ |
| 5 | binary-search | Search Rotated Array (M) | Koko Eating Bananas (M): search on answer | ✅ |
| 6 | bfs | Level Order Traversal (M) | Rotting Oranges (M): multi-source grid | ✅ |
| 7 | backtracking | Subsets (M) | Combination Sum (M) | ✅ |
| 8 | tree-recursion | Max Depth (E) | Diameter of Binary Tree (E) | ✅ |
| 9 | heap | Kth Largest (M) | Merge K Sorted Lists (H) | ✅ |
| 10 | prefix-sum | Range Sum Query (E) | Subarray Sum = K (M) | ✅ |
| 11 | dp-1d | House Robber (M) | Coin Change (M) | ✅ |
| 12 | dp-2d | Unique Paths (M) | Longest Common Subsequence (M) | ✅ |
| 13 | union-find | Number of Provinces (M) | Redundant Connection (M) | ✅ |
| 14 | topo-sort | Course Schedule (M) | Alien Dictionary (H)* | ✅ |
| 15 | trie | Implement Trie (M) | Word Search II (H) | ✅ |
| 16 | monotonic-stack | Daily Temperatures (M) | Largest Rectangle in Histogram (H) | ✅ |

\* LeetCode Premium. We write our own statements and tests, so this only matters for submitting there.

## Design decisions (settled; don't revisit without a reason)

- **Format:** one self-contained offline HTML file. Vanilla JS, no framework, no CDN at runtime.
- **Spacing (user, 2026-10-15):** same roomy spacing as system-design and sql-databases: body 15.5px / line height 1.7, ~36px between sections, 20–24px card padding, 11×14px table cells, 9px between list items.
- **Version:** `VERSION` holds the guide's semver (1.0.0 on 2026-10-15). The build shows it as `vX.Y.Z` beside the title and in `<meta name="version">`, and fails if it isn't MAJOR.MINOR.PATCH. Bump PATCH for fixes, MINOR for new content or features, MAJOR for changes that break saved data (storage keys, backup format).
- **Theme:** Ocean, light only: white page, `#0b6a87` deep teal-blue accent, matching syntax colours. The user chose calm over vivid (2026-10-09) from previews of GitHub blue, Ultramarine, Ocean and Indigo. No theme picker.
- **Top bar:** "Algorithm Patterns" in the accent colour (19px bold, links Home), compact progress (`done / total`, links Home), language toggle. No subtitle.
- **Layout:**
  - **One page at a time.** Each section is a page addressed by its hash (`#two-pointers`). A problem hash (`#three-sum`) opens its pattern page and scrolls to the card. Prev / next outline buttons at the bottom; ← / → keys too (not while typing).
  - Sidebar with groups: Overview (Home, Cheat Sheet), Patterns, Practice (Pattern Drill), Reference (Decision Guide, Language Cheat Sheet).
  - Any element id in the hash opens the page containing it and scrolls to it (problems, cheat-sheet sections `#ls-<id>`).
  - Every block in a section shares the same left/right edges. Don't add `max-width` to individual blocks.
  - Mobile ≤ 760px: the sidebar becomes a chip row.
- **Page order:** Home → Cheat Sheet → patterns 1–16 → Pattern Drill → Decision Guide → Language Cheat Sheet. The Decision Guide is reference material, useful once the patterns are known.
- **Home:** intro + Continue button (first unfinished problem), how to use, progress stats + To review list, 16-pattern grid with status dots, and Your data (Export / Import / Reset all).
- **Pattern block order:** Signal → Core Idea → [Diagram | Template] → Pitfalls → Problems. Core Idea uses the same text style as Pitfalls.
- **Problem card order:** statement → example → Hint and Test cases (collapsed) → attempt editor → Reveal → solution side by side → key insight and complexity.
- **Solutions hidden until Reveal.** Keep the global rule `[hidden] { display: none !important; }`. Its absence once let `.pane { display: flex }` show solutions early. `ui_check.py` guards this.
- **No code execution in the browser** (user decision). Comparison is visual, side by side. A line diff was rejected because correct solutions differ structurally.
- **Editor:** syntax-highlighted as you type: a Prism-highlighted `<pre>` sits behind a transparent textarea with scroll kept in sync. Tab / Shift+Tab indent, Enter auto-indents (after `:` in Python; `def` / `do` / `if`… in Ruby), Esc leaves. Starts with the solution's signature line.
- **Copy and Export** on both the attempt and the solution. Export filenames: `<id>.py`, `<id>_solution.rb`.
- **Language:** one global Python/Ruby toggle, remembered.
- **Storage:**
  - `localStorage` (keys `sg.*`) auto-saves attempts, progress and language, with an in-memory fallback.
  - Backup is **Export / Import JSON**: `{app: "algo-patterns", version: 1, exported, data: {sg.*: string}}`. Import merges (overwrites matching keys only) and never wipes. Import doesn't check `app` / `version` yet.
  - **Reset all** (Home) confirms, then deletes every `sg.*` key and reloads.
  - Reason: browser storage is per-browser and per-file-path, and Safari is flaky on `file://`.
- **Progress:** "Review again" / "Got it" per problem. Status dots in the sidebar and on Home's pattern grid; Home's To review list replaced the old All / To review / Not done filter.
- **Rejected:** a separate Python vs Ruby page (folded into the Language Cheat Sheet as ⚠ rows), one long scrolling page (replaced by pages), the progress filter, a "More practice" list per pattern, a Run-tests button, a generic "how to talk through a problem" script, a multi-theme picker.

## Work order

1. ✅ **Harness: structured inputs.** Done. See *Node values* under Content rules.
2. ✅ **Harness: class-design problems.** Done. See *Class-design tests* under Content rules.
3. ✅ **Diagram types.** Set with `diagram.type`. Keep them data-driven in YAML and legible on mobile. A note wider than its drawing widens the SVG automatically.
   - `array` (default) frame: `{values, marks: {L: i}, window: [i, j], hit: [i], note}`. Values can be any short text (✗ / ✓ for a yes/no check).
   - `linked` frame: `{values, loop: i (tail → node i), marks, hit, note}`. Marks on the same node go in one key: `{S F: 0}`.
   - `intervals` frame: `{bars: [[s, e]], lanes: [row per bar] (default one row each), hit, cut: {at, label} (dashed line), note}`. All frames share one x-scale.
   - `grid` frame: `{rows: [[…]], labels: [row names], cols: [column headers], marks: {i: col}, hit: [[r, c]], win: [[r, c]] or "all", note}`. `null` = no cell, `""` = empty cell. Used for BFS rings, the prefix / dp rows, the DP table and the monotonic stack.
   - `tree` frame: `{tree: node or [roots], up: true (arrows to parent), note}`, where node = `{v, c: [children; ~ = empty slot], hit, win, mark, b: badge, e: edge label}`. Laid out automatically. Used for backtracking, tree recursion, heap, union-find and trie.
   - `graph` frame: `{nodes: {id: [col, row]}, edges: [[from, to]], badge: {id: text}, hit, win, note}`, directed. YAML anchors (`&n` / `*n`) avoid repeating nodes across frames.
4. ✅ **Write patterns 3–16** in batches of 2–3. After each batch run build + `ui_check.py`, extend the problem ids in `ui_check.py`, and get user review before the next batch.
5. ✅ **Ruby heap:** done as the #9 pattern `helper` (a `MinHeap` class) rather than inside a pitfall, because code doesn't fit a bullet. A pitfall points to it. No gems.
6. **Next:** user review of #6–16; anything they flag goes here.
7. ✅ **Language Cheat Sheet:** all 16 sections are done, the traps are folded in, and the Python vs Ruby page is retired. Batch 3 awaits review.

## Known gaps

- Alien Dictionary can have several valid orders. Its tests use inputs with exactly one, so exact comparison works (the statement says so).
- Same-direction Two Pointers appears in the template but no problem practices it. This was accepted, because Fast & Slow (#3) drills the same movement.
- Page size is 176 KB with all 16 patterns.
- Pattern and problem ids share one HTML id space, so a problem can't reuse its pattern's id (Merge Intervals the problem is `merge-overlapping`). `build.py` fails on duplicates.

## Working rules (user preferences)

- **Plan first.** State the plan and assumptions and get approval before implementing. Surface tradeoffs; push back when warranted. Concise answers.
- **Never delete files.** Move them to a `delete/` folder instead.
- **Log every file change** to `file-mods.log` (markdown): date, time, path, and 1–2 lines on what changed.
- **Never publish** an Artifact or share a link without approval.
