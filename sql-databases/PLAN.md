# SQL Databases Study Guide — Plan

A single offline HTML page for **backend / staff-level interview prep on SQL databases** (user, 2026-10-15). Third guide in the set, built like `../algo-patterns` and `../system-design`: content in YAML, `build.py` validates it and renders one self-contained HTML file, and progress is saved in the browser.

It combines the two formats, because SQL interviews test two things:
- **Writing queries** (Part A), which works like algo-patterns: you write SQL in a scratch editor, then reveal a verified solution beside it, along with its expected result table.
- **Knowing the database** (Part B), which works like system-design blocks: design, indexes, planning, transactions, locking and internals, with quick checks.

Weight goes to Part B. Part A covers the querying a backend engineer is expected to do fluently, not analytics-round volume.

## Status (2026-10-15)

- **Plan approved** (user, 2026-10-15): backend / staff focus; no query execution in the browser; MySQL differences as ⚠ notes, no dialect toggle; setup and DDL (creating and dropping databases and tables) covered in the guide.
- **Draft approved (2026-10-15):** user said go ahead with everything.
- **All content written (2026-10-15), awaiting user review:** 17 topics (9 Part A, 8 Part B), 28 problems, Cheat Sheet (17 rows + 4 syntax groups), Technique Drill (30 questions), Glossary (74 terms). 135 solutions, snippets and cheat rows run and match against Postgres 18; 304 KB page; 73/73 UI checks pass.
- **Harness negative-tested twice:** wrong expected rows, wrong DDL test outcomes, a non-sargable solution under `uses_index`, a wrong final-state query, a wrong non-transactional snippet and an erroring cheat row each fail the build.

## Settled decisions

- **Dialect: PostgreSQL** (18 locally; content targets 14+ and tags newer features with `since`). Where MySQL (InnoDB, 8.0+) behaves differently, add a ⚠ note. No dialect toggle.
- **No query execution in the browser** (user, 2026-10-15), same as the other guides. You compare your attempt against the solution and the expected result table. To run queries for real, the Practice Dataset page has a copyable setup script for a local `psql`.
- **Every query is verified at build time.** `build.py` starts a throwaway Postgres cluster (`initdb` + `pg_ctl` in a temp dir, on a Unix socket, with no network port), loads the dataset, and runs every solution and snippet. A wrong result or an error fails the build, and no HTML is written. It uses `psql` as a subprocess, so the build needs no Python driver.
- **Expected results are written by hand**, not captured from the solution, so the check is independent of it.
- **Each problem runs in a transaction that is rolled back** (Postgres DDL is transactional), so problems can't affect each other. Statements that can't run inside a transaction (`CREATE DATABASE`, `VACUUM`, `CREATE INDEX CONCURRENTLY`) are marked `run: false` and only shown.
- Inherited from the other guides: one offline HTML file, vanilla JS, no CDN at runtime, Ocean theme (light only, `#0b6a87`), roomy spacing (line height 1.7, ~36px between sections, 20–24px card padding), hash-routed pages with prev / next and ← / → keys, a sidebar that becomes chips at ≤ 760px, the `[hidden] { display: none !important }` guard, and Export / Import / Reset of saved data.
- **Version:** `VERSION` holds the guide's semver (1.0.0 on 2026-10-15). The build shows it as `vX.Y.Z` beside the title and in `<meta name="version">`, and fails if it isn't MAJOR.MINOR.PATCH. Bump PATCH for fixes, MINOR for new content or features, MAJOR for changes that break saved data (storage keys, backup format).
- **Storage prefix `sq.`** (algo uses `sg.`, system-design `sd.`; all `file://` pages share one localStorage in Chrome). The backup is `{app: "sql-databases", version: 1, …}`.
- **SQL highlighting:** Prism core + `sql`, vendored and inlined as in algo-patterns. The editor is algo's highlighted-textarea editor with SQL indentation rules.
- **Overlap with `../system-design`:** its Storage Engines, Replication and Partitioning blocks stay at the architecture level. This guide goes into the Postgres-level detail and links there for the rest.

## Topics

### Part A: Setup & querying (each has 2 verified problems: one canonical, one disguised)

| # | id | Topic | Covers |
|---|---|---|---|
| 1 | setup-ddl | Setup & DDL | `psql` essentials (`\l \c \dt \d+ \x \timing`), `createdb` / `dropdb`, `CREATE` / `DROP DATABASE` (and why you can't drop the one you're connected to), schemas and `search_path`, `CREATE TABLE` with types and defaults, identity columns vs `serial`, `ALTER TABLE`, `DROP … IF EXISTS … CASCADE`, `TRUNCATE` vs `DELETE`, roles and `GRANT` basics |
| 2 | joins | Joins & set operations | outer-join filter trap (`ON` vs `WHERE`), semi / anti joins, `NOT IN` with NULLs, join fan-out, `UNION` vs `UNION ALL`, `EXCEPT` / `INTERSECT` |
| 3 | aggregation | Aggregation | `COUNT(*)` vs `COUNT(col)` vs `COUNT(DISTINCT)`, `HAVING`, `FILTER`, conditional sums, `GROUPING SETS` / `ROLLUP`, `string_agg` / `array_agg` |
| 4 | nulls-types | NULLs, types & dates | three-valued logic, `IS DISTINCT FROM`, `COALESCE` / `NULLIF`, integer division, `numeric` vs `float` for money, `timestamptz` and time zones, `date_trunc`, `generate_series` to fill gaps |
| 5 | subqueries | Subqueries, CTEs & LATERAL | correlated subqueries, CTE inlining vs `MATERIALIZED`, `LATERAL` for top-N per row, scalar subquery pitfalls |
| 6 | windows | Window functions | `ROW_NUMBER` / `RANK` / `DENSE_RANK`, running totals, `LAG` / `LEAD`, ROWS vs RANGE frames, `PARTITION BY` vs `GROUP BY` |
| 7 | recursive | Recursive CTEs | hierarchies (org chart, categories), path building, depth limits and cycle guards (`CYCLE` clause) |
| 8 | patterns | Classic query patterns | top-N per group, gaps and islands, dedup keeping one row, pivot with `FILTER`, sessionization, retention and funnels, median / percentiles |
| 9 | writes | Writing data | upsert with `ON CONFLICT`, `MERGE`, `RETURNING`, `UPDATE … FROM`, deleting duplicates, batched backfills |

### Part B: Design & internals (concept pages with quick checks; some have verified problems)

| # | id | Topic | Covers |
|---|---|---|---|
| 10 | schema-design | Schema design | normal forms in practice, when to denormalize, surrogate vs natural keys, UUIDv4 vs UUIDv7 vs bigint, soft deletes, JSONB vs columns, multi-tenant layouts |
| 11 | constraints | Constraints & integrity | FK (and indexing FK columns), `CHECK`, partial `UNIQUE`, exclusion constraints (no overlapping bookings), deferrable constraints, `NOT VALID` + `VALIDATE` |
| 12 | indexes | Indexes | B-tree internals, composite order, covering (`INCLUDE`), partial, expression, GIN / GiST / BRIN, index-only scans and the visibility map, cost of unused indexes |
| 13 | query-planning | Query planning & EXPLAIN | scan types, join algorithms (nested loop, hash, merge), statistics and misestimates, reading `EXPLAIN (ANALYZE, BUFFERS)`, sargability, `pg_stat_statements` |
| 14 | isolation | Transactions & isolation | anomalies (dirty, non-repeatable, phantom, lost update, write skew), Read Committed / Repeatable Read / Serializable in Postgres vs MySQL, serialization failures and retries |
| 15 | locking | Locking & concurrency | row locks (`FOR UPDATE` / `FOR SHARE` / `NOWAIT` / `SKIP LOCKED`), job queues in SQL, deadlocks, advisory locks, optimistic locking with a version column, DDL lock queues and `lock_timeout` |
| 16 | mvcc-wal | MVCC, WAL & VACUUM | tuple versions, HOT updates, bloat, autovacuum tuning, long transactions, XID wraparound, WAL, checkpoints and `full_page_writes` |
| 17 | scaling | Running Postgres at scale | connection pooling (PgBouncer modes), read replicas and lag, declarative partitioning, zero-downtime migrations, sharding options (Citus, app-level), backups and PITR |

Problems in Part B are **DDL problems**: write the schema or constraint, and the build checks it with statements that must succeed or must fail (for example, an overlapping booking must be rejected). Concurrency topics (14, 15) use the timeline diagram and text checks; their two-session behaviour is not verified at build time.

## Site-wide pages

| Page | Content |
|---|---|
| Home | intro, Continue, progress, To review, topic grid, Your data |
| Cheat Sheet | one row per topic (when / move / gotcha) plus a syntax quick-reference; Print button |
| Practice Dataset | the schema diagram, a few rows of each table, and the **full setup script**: `DROP DATABASE IF EXISTS` / `CREATE DATABASE`, all `CREATE TABLE`s, seed data. Copy it into `psql` to practice locally. The build loads the same script, so it can't drift. |
| Technique Drill | "which technique solves this?", 4 options, keys 1–4 + Enter (like system-design's Block Drill) |
| Glossary | terms A–Z with live filter, each linking to its topic |

Page order: Home → Cheat Sheet → Practice Dataset → Part A (1–9) → Part B (10–17) → Technique Drill → Glossary. Sidebar groups: Overview, Setup & querying, Design & internals, Practice, Reference. Progress counts problems (Part A and B) plus Part B topics.

## Practice dataset

One small e-commerce + org schema, small enough to show every row of a result (~10–40 rows per table):
- `users` (id, email, country, created_at, referred_by → users)
- `products` (id, name, category, price)
- `orders` (id, user_id, status, created_at)
- `order_items` (order_id, product_id, qty, unit_price)
- `events` (user_id, type, at), for sessionization, funnels and retention
- `employees` (id, name, manager_id → employees, dept, salary, hired_on), for hierarchies and top-N per group

Seed data deliberately contains the edge cases the problems need: NULLs, ties, users with no orders, gaps in dates, duplicate rows, a cycle-free hierarchy several levels deep.

## Content schema

### Topic (`topics/<id>.yaml`)
| Field | Rule |
|---|---|
| `signal` | 3–5 cues that call for this topic. |
| `idea` | Core Idea, **2–4 lines**. |
| `diagram` | Optional. Types: `timeline` (new), `plan` (new), `table` (rows before / after, e.g. a window frame). |
| `numbers` | Optional key numbers `{k, v}`. |
| `tables` | Optional `{title, cols, rows}`. |
| `snippets` | Optional syntax rows `{task, sql, out?, note?, mysql?, run?}`. Each runs in the build (rolled back). Setup & DDL is mostly snippets. |
| `pitfalls` | **4–6**, beyond the basics. |
| `depth` | Part B: **3–6** staff-level points. |
| `checks` | Part B: **3–5** quick checks `{q, a}`. |
| `problems` | Part A: **exactly 2**. Part B: 0–2 (DDL problems). |

MySQL differences: a topic-level `mysql:` list renders as a ⚠ box after the pitfalls / depth; `mysql:` on a snippet or problem renders as an inline note.

### Problem
```yaml
- id: top-earners-per-dept
  title: Top 2 earners per department
  variant: canonical            # or disguise
  statement: …
  hint: …                       # a nudge, not the answer
  setup: |                      # optional extra SQL run before the solution (rolled back)
  solution: |
    SELECT …
  expect:                       # written by hand; the build compares
    cols: [dept, name, salary]
    rows: [[eng, Ada, 190000], …]
    order: true                 # false → compare as a multiset
  tests:                        # DDL problems instead of expect
    - {sql: "INSERT …", ok: true}
    - {sql: "INSERT …", error: exclusion_violation}   # SQLSTATE condition name
  insight: …                    # shown after reveal
  mysql: …                      # optional ⚠ note
```
- **Query problems** (`expect`): setup (+ solution, when a `check` query reads the result) run with output off; the last statement's output is compared. Numbers compare by value (`200` = `200.00`), YAML `null` = SQL NULL, booleans print as `t` / `f`, dates as ISO. `order: false` compares as a multiset.
- **DDL problems** (`tests`): after setup + solution, each test runs in its own sub-transaction (a `DO` block), **in order, with effects kept**: `ok: true`, `error: <condition name>` (mapped to SQLSTATE in `build.py`), or `uses_index: true` (EXPLAIN with `enable_seqscan = off` must show an index). Optional `note` per test. The page lists the tests under “Must pass” before reveal.
- **Solution lines ≤ 58 chars** (build-enforced), so the revealed side-by-side pane never scrolls at 1280px.
- **Snippets** with `out` must have exactly one result-producing statement. `run: false` snippets show a “not run” tag. `shell: true` snippets (shell or psql meta-commands) are shown with a `$` prompt and never run. `tx: false` snippets (`CREATE DATABASE`, `VACUUM`, `CONCURRENTLY`, explicit `BEGIN … COMMIT`) run without a wrapping transaction in a throwaway `scratch` clone of `practice`, dropped afterwards.
- **Query problems with `uses_index: true | <index name>`**: besides matching `expect`, the solution's EXPLAIN (seq scans off) must use an index / that index. DDL tests take the same value.
- **DDL problems may add `check` + `expect`**: after the tests, the check query's result is compared (the page shows it as “Then this query”).
- **Sequences are reset before every run.** Sequences aren't transactional, so rolled-back inserts would shift later ids; the build resets every identity sequence to `max(id)` at the start of each run so results never depend on run order.
- **Timeline frames** may set their own `sessions` (e.g. a 3-session lock-queue frame in a 2-session diagram).
- **Cheat Sheet** `pages/cheat.yaml`: `topics` rows `{id, when, move, gotcha}` covering every written topic in catalog order (build-enforced), and `syntax` groups of `{task, sql, run?}` rows, each run by the build. **Technique Drill** `pages/drill.yaml`: `{prompt, answer, distractors (3), why}`, all topic ids. **Glossary** `pages/glossary.yaml`: `{term, def, see}`, `see` a topic id, no duplicates.

### New diagram types
All three use frame tabs + a note per frame, like system-design's `arch`.
- `timeline`: `sessions: [T1, T2]`; frame `steps: [{t, sql, out?, mark?}]`, marks `sees | wait | error | bad | ok`. A `sql` starting with `(` renders as an italic stage direction (“(update resumes)”). Used for isolation anomalies, lost updates, deadlocks and `SKIP LOCKED`.
- `plan`: frame `query` + `plan: [{d (depth), op, on?, detail?, est?, act?, ms?, mark: bad | good}]`. Numbers are illustrative and the caption says so.
- `table`: `cols`, `rows` (first column = partition; a rule is drawn between partitions); frame `expr` (its first word heads the output column), `cur` (row index), `win` (row indexes in the frame), `out` (one value per row, `null` = NULL).

## Files

| File | Role |
|---|---|
| `guide.yaml` | Catalog: Part A and B topics in order. |
| `topics/<id>.yaml` | One topic per file. |
| `data/dataset.sql` | The practice dataset setup script (shown on the Practice Dataset page and loaded by the build). |
| `pages/*.yaml` | `cheat`, `drill`, `glossary` (schemas under Content schema). |
| `build.py` | Starts a throwaway Postgres, validates schema and references, runs every solution, snippet and test, then renders `dist/study-guide-sqldb.html`. Refuses to write HTML on any failure. |
| `template.html` | Forked from system-design, plus algo's editor and Prism. |
| `vendor/` | Prism core + sql. |
| `tests/ui_check.py` | Headless-browser checks. Run after every template change. |
| `dist/study-guide-sqldb.html` | **Build output.** Never hand-edit. |
| `VERSION` | Guide version (semver), shown in the page. |
| `file-mods.log` | Change log. |

## Work order

1. ✅ **Draft:** harness (throwaway Postgres, result comparison, DDL tests), template, `dataset.sql`, the Practice Dataset page, and 3 topics: **Window functions** (Part A problems), **Indexes** (Part B with a `plan` diagram) and **Transactions & isolation** (`timeline` diagram). Then the user reviews the format.
2. ✅ Part A topics (2 batches).
3. ✅ Part B topics (2 batches).
4. ✅ Site-wide pages: Cheat Sheet, Technique Drill, Glossary.
5. **Next:** user review of everything after the draft; anything they flag goes here.

## Working rules (user preferences)

- **Plan first.** State the plan and assumptions and get approval before implementing. Surface tradeoffs; push back when warranted. Concise answers.
- **Never delete files.** Move them to a `delete/` folder instead.
- **Log every file change** to `file-mods.log` (markdown): date, time, path, and 1–2 lines on what changed.
- **Never publish** an Artifact or share a link without approval.
