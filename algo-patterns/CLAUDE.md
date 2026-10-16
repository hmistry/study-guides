# Algorithm Patterns Study Guide

Read `PLAN.md` before any work. It holds every settled decision, the content rules, the approved problem list and the work order.

## Commands
- `python3 build.py`: tests all solutions (Python + Ruby), then builds `dist/study-guide-algo.html`. It must pass before anything ships.
- `python3 tests/ui_check.py`: headless browser checks. Run after any change to `template.html`.

## Rules
- Content lives in `guide.yaml` (catalog), `topics/<id>.yaml` (one pattern each) and `pages/*.yaml` (decision guide, drill, language sheet). Never hand-edit `dist/study-guide-algo.html`; it's build output. The version lives in `VERSION`.
- Plan first: state the plan and assumptions and get approval before implementing.
- Never delete files. Move them to `delete/`.
- Append every file change to `file-mods.log` (date, time, path, 1–2 line summary).
- Never publish anything externally without approval.
