# System Design Study Guide — Plan

A single offline HTML page for **senior / staff-level system design interview prep**. Sister project to `../algo-patterns` and built the same way: content in YAML, `build.py` validates it and renders one self-contained HTML file, and progress is saved in the browser.

Two use cases drive the design (user, 2026-10-15):
1. **Studying.** Work a case one step at a time: write your notes, reveal the reference for that step, compare, and go on to the next step.
2. **Review the night before.** One **Reveal all** switch shows the whole reference at once, to check what you remember.

## Status (2026-10-15)

- **All content written:** 16 blocks + 12 cases, 89 verified estimates, 305 KB page; build and 84 UI checks pass. The user approved the draft format (2026-10-15) and asked for roomier spacing (done), then for everything to be built in batches. The 25 pages after the draft are **awaiting user review**.
- **Site-wide pages done (2026-10-15):** Cheat Sheet, Interview Framework, Estimation Drill (12 problems), Block Drill (24 questions), Tradeoff Glossary (49 terms). 107 estimates verified; 352 KB; 100 UI checks pass. Awaiting user review together with the 25 pages above.

## Files

| File | Role |
|---|---|
| `guide.yaml` | Catalog (all 16 blocks + 12 cases, in order). Site-wide pages will go here later. |
| `blocks/<id>.yaml` | One building block per file. |
| `cases/<id>.yaml` | One case study per file. |
| `pages/*.yaml` | Site-wide pages: `cheat`, `framework`, `est-drill`, `drill`, `glossary` (schemas below). |
| `build.py` | Validates schema, references, diagrams and tables, recomputes every estimate, then renders `dist/study-guide-sysd.html`. Refuses to write HTML on any failure. |
| `template.html` | Page shell: CSS + vanilla JS renderer. Forked from algo-patterns (no Prism, no language toggle, no code editor). |
| `tests/ui_check.py` | Headless-browser checks. Run after every template change. |
| `dist/study-guide-sysd.html` | **Build output.** Never hand-edit. |
| `VERSION` | Guide version (semver), shown in the page. |
| `file-mods.log` | Change log. |

```bash
python3 build.py              # validate + build → dist/study-guide-sysd.html
python3 tests/ui_check.py     # after every template change
```

## Content rules

### Text
Answer and prompt fields use a small Markdown subset (fenced code must start at column 0, never inside a list item; the build checks this) that `template.html` renders: paragraphs, `-` / `1.` lists (nest with 2 spaces), `**bold**`, `` `code` ``, fenced ``` blocks, `| tables |` (header row + `|---|`), and `> ` callouts. `build.py` checks that every table row has the same number of cells.

### Building block (`blocks/<id>.yaml`)
| Field | Rule |
|---|---|
| `signal` | 3–5 interview cues that call for this block. |
| `idea` | Core Idea, **2–4 lines**: what it buys, what it costs, and the decision it drives. |
| `diagram` | Optional `arch` diagram (below). Shows the mechanism, not one product. |
| `numbers` | Optional key numbers `{k, v}`, shown beside the diagram. |
| `tables` | Optional `{title, cols, rows}` comparison tables (options × tradeoffs). |
| `pitfalls` | **4–6**, beyond the basics: the mistakes seniors still make. |
| `depth` | **3–6** "Staff-level depth" points: what to bring up without being asked. |
| `checks` | **3–5** quick checks. Either text (`q`, `a`: think, then reveal) or numeric (`q`, `given`, `calc`, optional `a`). |

### Case study (`cases/<id>.yaml`)
`prompt` (the interview question), `blocks` (catalog ids it exercises), then `steps` in framework order. Each step has `id`, `title`, `min` (time budget out of 45), `ask` (what to cover) and `answer`. Steps can also have:
- `given` + `calc`: verified estimates (the estimation step).
- `diagram`: the high-level design.
- `items`: deep-dive questions `{id, q, answer}`, each revealed on its own.

Standard steps: Requirements (5) → Estimation (5) → API (4) → Data model (5) → High-level design (8) → Deep dives (15) → Wrap-up (3). The wrap-up covers what breaks first, what to monitor, what makes a staff answer, and common mistakes.

### Site-wide pages (`pages/`)
| File | Content | Build checks |
|---|---|---|
| `cheat.yaml` | `blocks: [{id, when, move, num}]`, `cases: [{id, crux, key}]`, `numbers: [{k, v}]`; Print button prints this page alone | rows list every catalog id once, in order |
| `framework.yaml` | `intro`, `steps: [{id, title, min, goal, do, staff, avoid}]`, `throughout` | every case's step ids must equal the framework's, in order |
| `est-drill.yaml` | `problems: [{q, given, calc, a}]`, same format as numeric checks | every `show` recomputed |
| `drill.yaml` | `items: [{prompt, answer, distractors (3), why}]`, shuffled, keys 1–4 + Enter | all ids are blocks, 4 distinct options |
| `glossary.yaml` | `terms: [{term, def, see}]`, sorted A–Z on render, live filter | `see` is a block id; no duplicate terms |

Page order: Home → Cheat Sheet → Interview Framework → blocks 1–16 → cases C1–C12 → Estimation Drill → Block Drill → Tradeoff Glossary. Sidebar groups: Overview, Building blocks, Case studies, Practice, Reference. Progress still counts only blocks and cases (28).

### Numeric estimates (`given` / `calc`)
```yaml
given: {dau: "500e6", posts: 2}          # strings are evaluated (YAML reads 500e6 as text)
calc:
  - {name: w, ask: Average write QPS, unit: /s, expr: "dau * posts / 86400", show: "≈ 12K/s"}
  - {ask: Peak (3×), unit: /s, expr: "w * 3", show: "≈ 35K/s"}
```
- `build.py` evaluates `expr`, which may use `+ - * / // % **`, `min`, `max`, `ceil`, `log2`, `given` names and earlier `name`s.
- It fails the build if `show` is more than 15% off the computed value. `show` suffixes K/M/B/T must touch the digits (`12K`); units take a space (`3 TB`).
- On the page you type a number in the given unit (`12K`, `3.5e9` and `12,000` all work), then press Check:
  - ✓ close: within 25%.
  - ~ ballpark: within 3×.
  - ✗ off: anything else, with the factor it's off by.

### `arch` diagram
```yaml
diagram:
  type: arch
  caption: …
  nodes: {app: {label: App, at: [1, 1], kind: service, sub: optional 2nd line}}   # kind: client | service | db | cache | queue
  edges: [[client, app], …]                    # faint connections, shown in every frame
  frames:
    - {title: Read · hit, flow: [[client, app, "GET"]], hit: [cache], win: [app], note: …}
```
`at` is `[col, row]`; fractions are allowed. **Build-enforced limits:** at most 5 columns (col 0–4); box label ≤ ~14 characters and subtitle ≤ ~16 (fewer on `queue` boxes, whose glyph takes the right edge); a label on an arrow between two boxes in the same row must fit the gap (~14 characters). Labels on diagonal arrows flip sides automatically when they would overlap a box. Quote any YAML value containing `?`, `: ` or commas inside `[ ]`. Frames are tabs over a single drawing. `flow` edges are drawn as accent arrows; when an edge and its reverse are both in the flow, the two are offset. `hit` marks green ("served here") and `win` marks tinted ("involved"). Notes are HTML under the drawing, so they wrap. On mobile the drawing scrolls sideways inside its box, never the page.

## Building blocks (16)

| # | id | Block | Status |
|---|---|---|---|
| 1 | estimation | Estimation | ✅ |
| 2 | apis | APIs & Protocols | ✅ |
| 3 | load-balancing | Load Balancing & Gateways | ✅ |
| 4 | caching | Caching | ✅ |
| 5 | cdn-blob | CDN & Object Storage | ✅ |
| 6 | datastores | Choosing a Datastore | ✅ |
| 7 | storage-engines | Storage Engines & Indexes | ✅ |
| 8 | replication | Replication | ✅ |
| 9 | partitioning | Partitioning | ✅ |
| 10 | consistency | Consistency Models | ✅ |
| 11 | queues | Queues & Streams | ✅ |
| 12 | dist-transactions | Distributed Transactions | ✅ |
| 13 | consensus | Consensus & Coordination | ✅ |
| 14 | rate-limits-ids | Rate Limiting & Unique IDs | ✅ |
| 15 | reliability | Reliability Patterns | ✅ |
| 16 | observability | Observability & Ops | ✅ |

## Case studies (12)

| # | id | Case | Main lesson | Status |
|---|---|---|---|---|
| 1 | url-shortener | URL Shortener | ID generation, read-heavy caching | ✅ |
| 2 | rate-limiter | Distributed Rate Limiter | atomic counters, multi-region limits | ✅ |
| 3 | kv-store | Key-Value Store | partitioning, quorums, gossip | ✅ |
| 4 | news-feed | News Feed | fan-out on write vs read, celebrities | ✅ |
| 5 | chat | Chat / Messaging | WebSockets, presence, ordering, offline | ✅ |
| 6 | notifications | Notification System | queues, retries, providers, dedup | ✅ |
| 7 | typeahead | Typeahead | prefix index, top-k precompute | ✅ |
| 8 | web-crawler | Web Crawler | frontier, politeness, dedup | ✅ |
| 9 | video-streaming | Video Streaming | transcoding pipeline, CDN, ABR | ✅ |
| 10 | file-sync | File Sync | chunking, content hashing, conflicts | ✅ |
| 11 | proximity | Ride Sharing / Proximity | geo-indexing, location updates | ✅ |
| 12 | ticket-booking | Ticket Booking | contention, holds with TTL | ✅ |

## Design decisions

Inherited from algo-patterns: one offline HTML file, vanilla JS, no CDN at runtime, Ocean theme (light only, `#0b6a87`), hash-routed pages with prev / next and ← / → keys, a sidebar that becomes chips at ≤ 760px, the `[hidden] { display: none !important }` guard, and Export / Import / Reset of saved data.

New here:
- **Storage prefix `sd.`**, not `sg.`. Chrome gives all `file://` pages one shared localStorage, so the two guides would otherwise collide, and algo's Reset all would wipe this guide's data. The backup is `{app: "system-design", version: 1, …}`.
- **Version:** `VERSION` holds the guide's semver (1.0.0 on 2026-10-15). The build shows it as `vX.Y.Z` beside the title and in `<meta name="version">`, and fails if it isn't MAJOR.MINOR.PATCH. Bump PATCH for fixes, MINOR for new content or features, MAJOR for changes that break saved data (storage keys, backup format).
- **Spacing (user, 2026-10-15):** roomy, not dense. Body line height 1.7, ~36px between sections, 20–24px card padding, 11×14px table cells.
- **Progress is per page** (each block and case): Got it / Review again in the page header.
- **Case steps:** notes textarea on the left, reference on the right once revealed (stacked below 960px). **Reveal all** opens every step and deep dive, makes the references full width, and hides empty notes. Notes auto-save.
- **Block quick checks** have no textarea: think, then reveal. Numeric checks have inputs and a Check button. A **Reveal all** covers the checks too.
- **No syntax highlighting** (no code to run). API and schema blocks are plain monospace.
- **Level:** senior / staff. Assume the basics are known; spend the words on tradeoffs, failure modes and numbers.
- **`sql-databases/` overlap:** blocks 6–9 stay at the architecture level (which store, how it scales); SQL, query and isolation detail belongs to that guide.

## Work order

1. ✅ **Draft** (Estimation, Caching, URL Shortener) + format: approved by the user, then spacing loosened.
2. ✅ Blocks in 4 batches (user asked for all of them without stopping between batches).
3. ✅ Cases in 4 batches.
4. ✅ Site-wide pages: Cheat Sheet, Interview Framework, Estimation Drill, Block Drill, Tradeoff Glossary.
5. **Next:** user review of everything after the draft; anything they flag goes here.

## Working rules (user preferences)

- **Plan first.** State the plan and assumptions and get approval before implementing. Surface tradeoffs; push back when warranted. Concise answers.
- **Never delete files.** Move them to a `delete/` folder instead.
- **Log every file change** to `file-mods.log` (markdown): date, time, path, and 1–2 lines on what changed.
- **Never publish** an Artifact or share a link without approval.
