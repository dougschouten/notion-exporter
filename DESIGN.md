# Notion Exporter — Design Document

## Purpose

A command-line tool that exports a Notion database to a structured CSV file. Each top-level database entry becomes a parent row; page content (text blocks, toggle sections, embedded sub-databases) within the date range becomes child sub-rows, with full Markdown formatting preserved. Intended for periodic technical-work summarisation from Notion project databases.

---

## Architecture

```
notion_exporter/
├── cli.py               # Entry point, argument parsing, orchestration
├── notion_client.py     # Notion REST API wrapper (auth, pagination, retry)
├── database_fetcher.py  # Database metadata, property extraction, entry querying
├── property_selector.py # Curses-based interactive TUI for field selection
├── page_parser.py       # Recursive block traversal, heading accumulation
├── text_formatter.py    # Notion rich_text → Markdown conversion
├── csv_writer.py        # CSV assembly and file output
├── progress.py          # ANSI terminal progress display
└── tests/               # Per-task test scripts (mix of live and unit tests)
```

### Dependency graph

```
cli.py
 ├── notion_client.py
 ├── database_fetcher.py ──► notion_client.py
 ├── property_selector.py
 ├── page_parser.py ──────► notion_client.py
 │                     └──► database_fetcher.py
 │                     └──► text_formatter.py
 ├── csv_writer.py
 └── progress.py
```

---

## CSV Schema

```
type, id, parent_id, title, people, date, technical_work_data
```

| Column | Entry rows | Sub-item rows |
|---|---|---|
| `type` | `entry` | `subitem` |
| `id` | 8-char MD5 hash of Notion page UUID | `""` |
| `parent_id` | `""` | `id` of parent entry |
| `title` | Notion page Name property | Toggle header / sub-DB page title / `""` for plain text |
| `people` | Semicolon-joined names from selected person field(s) | Inherited from parent |
| `date` | Value from selected date field | `created_time` of the block/page, YYYY-MM-DD |
| `technical_work_data` | `""` | Markdown-formatted block content |

All fields are quoted with `csv.QUOTE_ALL`, so commas, quotes, and embedded newlines in `technical_work_data` are safe for any standards-compliant CSV parser.

---

## Key Design Decisions

### No Notion SDK — direct REST calls
Using `requests` directly gives full control over pagination, rate limiting, and error handling without taking on an SDK dependency. The Notion API is simple enough that the wrapper (`notion_client.py`) is ~60 lines.

### Date field selection includes built-in timestamps
Many databases have empty or sparse user-defined `date` properties. Two synthetic options — `last_edited_time (built-in)` and `created_time (built-in)` — are always offered alongside real date properties. These use Notion's timestamp filter syntax (`{"timestamp": "last_edited_time", ...}`) rather than the property filter syntax, handled transparently in `database_fetcher.fetch_entries`.

### Stable entry IDs via MD5 hash
Each entry's `id` is the first 8 hex characters of the MD5 of its Notion page UUID (uppercased, e.g. `C20CA647`). This is stable across repeated exports of the same database, allowing downstream tools to join on `id`/`parent_id` without drift.

### Heading accumulation instead of standalone heading sub-rows
`heading_1/2/3` blocks do not produce their own sub-rows. Instead they are held in a `pending_headings` buffer and prepended to the next non-heading block's `technical_work_data` (e.g. `## About this project\n\nImplementing heterogeneous layer model…`). This produces richer, coherent content cells rather than stubs. If a heading has no subsequent block, it is flushed as its own sub-row so nothing is lost.

### Toggle depth — one level only
Toggle blocks are expanded one level. Children's text is concatenated into a single `technical_work_data` cell; the toggle's own header text becomes the `title`. Deeper nesting is not traversed. This is a deliberate tradeoff: fully recursive traversal risks very large cells and deeply nested Notion pages are rare in the target use case.

### Sub-database date field — lazy prompt and cache
When a `child_database` block is encountered, the tool checks whether the parent's chosen date field exists in the sub-database. If yes, it uses it automatically. If not, a curses `single_select` prompt fires so the user picks one. The choice is cached by database ID so each unique sub-database is only prompted once per run.

### Warnings are ephemeral on TTY, plain text otherwise
All `[WARN]` output goes to `stderr` and is routed through `ProgressStderr`, which calls `progress.warn()`. On a TTY the warning flashes on the message line of the progress display, then is overwritten by the next update. On a pipe/non-TTY it becomes a plain `[WARN] …` line. This keeps the CSV on `stdout` clean for piping while still surfacing problems.

### Progress display cursor accounting
The two-line progress footer (message line + bar line) is maintained using ANSI escape codes. The critical invariant: after every `_render()` call the cursor must sit at line N+2 (the baseline, 2 lines below the message line), so the next `\033[2A` (up 2) always lands exactly on the message line.

The fix for the macOS drift bug: after writing the bar line, use `\033[1B\r` (cursor **down** 1 existing line, return to col 0) instead of `\n`. `\n` would create a new line if at the terminal bottom, causing the terminal to scroll and invalidating the cursor position assumptions. `\033[1B` moves within the already-reserved area and never scrolls.

---

## Module Reference

### `notion_client.py` — `NotionClient`

Wraps all Notion REST calls. Base URL `https://api.notion.com/v1`, API version `2022-06-28`.

- **`get(path, params)`** / **`post(path, body)`** — single requests; non-2xx prints `[WARN]` and returns `None`
- **`paginate_post(path, body)`** / **`paginate_get(path, params)`** — generators that transparently follow `has_more`/`next_cursor` pagination
- **Retry logic** — HTTP 429 sleeps `Retry-After` seconds (default 1 s) and retries up to 3 times

---

### `database_fetcher.py`

- **`fetch_database_metadata(client, db_id)`** → raw properties dict from `GET /databases/{id}`
- **`extract_typed_properties(properties)`** → `{"date": [...], "people": [...]}`. Always appends `last_edited_time (built-in)` and `created_time (built-in)` as synthetic date options.
- **`fetch_entries(client, db_id, date_field, start_str, end_str)`** → paginates `POST /databases/{id}/query` with an `on_or_after`/`on_or_before` filter. Uses `{"timestamp": ...}` filter form for built-in timestamps; `{"property": ...}` form for user properties.
- **`parse_entry_properties(page, person_fields, date_field)`** → dict with `id` (MD5 hash), `title`, `people` (deduplicated list), `date`. Handles built-in timestamp extraction from page metadata directly rather than from the `properties` map.

---

### `property_selector.py` — curses TUI

Two reusable full-screen selectors built on Python's stdlib `curses`:

- **`single_select(title, rows, columns)`** — arrow keys navigate, Enter confirms. Returns selected row dict or `None` on ESC.
- **`multi_select(title, rows, columns)`** — Space toggles checkbox, Enter confirms (requires ≥1 selection). Returns list of selected row dicts.

Both render a formatted table with a bold title bar, column headers, separator, scrollable data rows (scroll window follows highlight), and an error message line at the bottom. `curses.wrapper` ensures the terminal is always fully restored even on exception.

---

### `text_formatter.py`

Converts Notion's `rich_text` arrays and block objects to Markdown strings.

- **`rich_text_to_markdown(rich_text_array)`** — processes each segment's annotations in order: `code` → `` `x` ``, `bold` → `**x**`, `italic` → `*x*`, `strikethrough` → `~~x~~`. Links wrap as `[text](href)`. Underline and color are discarded (no Markdown equivalent).
- **`block_to_markdown(block)`** — delegates inline content to `rich_text_to_markdown`, then applies block-level prefix: `#`/`##`/`###` for headings, `- ` for bullets, `1. ` for numbered lists, `- [ ]`/`- [x]` for to-dos, `> ` for quotes/callouts (with emoji icon if present), fenced ` ``` ` for code blocks. Returns `""` and prints `[WARN]` if `rich_text` key is absent.

---

### `page_parser.py`

Traverses a Notion page's block tree to produce sub-rows.

**Top-level entry point:** `parse_page(client, page_id, start, end, sub_db_date_cache, selector_fn, parent_date_field)`

Fetches all top-level blocks and dispatches by type:

| Block type | Handler | Output |
|---|---|---|
| `heading_1/2/3` | accumulated in `pending_headings` buffer | flushed into next block's content |
| `paragraph`, `bulleted_list_item`, `numbered_list_item`, `code`, `quote`, `callout`, `to_do` | `handle_text_block` | one sub-row if `created_time` in range; pending headings prepended |
| `toggle` | `handle_toggle` | one sub-row (toggle header → `title`, children's text concatenated → `technical_work_data`); one level deep only |
| `child_database` | `handle_child_database` | one sub-row per qualifying page; lazy date-field selection and caching |
| anything else | warn + skip | — |

All handlers check `block.created_time` against `[start, end]` (converted to UTC naive date for comparison). Every exception is caught and printed as `[WARN]` so processing always continues.

---

### `csv_writer.py`

- **`open_csv(output_path)`** → opens file, writes header, returns `(file, DictWriter)` with `QUOTE_ALL`
- **`write_parent_row(writer, row)`** — writes `type=entry` row; `technical_work_data` is always empty
- **`write_sub_row(writer, sub_row, people, parent_id)`** — writes `type=subitem` row with inherited people and parent_id
- **`auto_filename(start_str, end_str)`** → `notion_export_{start}_{end}.csv`

---

### `progress.py`

Two-line ANSI terminal footer with graceful TTY/non-TTY fallback.

**`ProgressDisplay(total, out)`**
- `update(n, msg)` — advance counter, show info message (cyan `●`)
- `warn(msg)` — show warning (yellow `⚠`)
- `info(msg)` — show informational message
- `finish(summary)` — advance to 100%, show green `✓`, leave footer in place

Cursor accounting: `_ensure_ready()` reserves 2 lines with `\n\n`. Each `_render()` does `\033[2A\r` (up 2, col 0), writes message line, does `\n\r\033[2K` (to bar line), writes bar, then `\033[1B\r` (down 1 existing line, col 0) to return to baseline. `\033[1B` never scrolls; `\n` would if at the terminal bottom.

**`ProgressStderr`** — `sys.stderr` replacement that buffers partial writes and routes completed `[WARN]` lines to `display.warn()`, all other lines to `display.info()`. The CLI installs this after the TUI exits and removes it before any sub-database curses prompt.

---

### `cli.py` — orchestration

Full pipeline in `main()`:

1. Parse args; validate dates; extract database ID from URL (regex for trailing 32-char hex)
2. Fetch database metadata
3. TUI: multi-select person fields; single-select date field
4. Query entries with date filter
5. Install `ProgressStderr` over `sys.stderr`
6. For each entry: parse properties → write parent row → parse page blocks → write sub-rows
7. Sub-database curses prompts temporarily restore real stderr around `curses.wrapper`
8. `display.finish()` prints summary; real stderr restored; summary lines printed

---

## Implementation History

| Task | Outcome |
|---|---|
| 1 — Scaffolding | argparse skeleton, URL → database ID extraction, date validation |
| 2 — Notion API client | Auth, pagination, 429 retry confirmed live (101 results, 15 properties) |
| 3 — Metadata fetcher | **Human checkpoint** — 2 people fields (`Contributors`, `Owner`), 1 date field (`Dates`) confirmed against Notion UI |
| 4 — Curses TUI | **Human checkpoint** — arrow-key navigation, Space toggle, terminal restore |
| 5 — Entry fetcher | **Human checkpoint** — 7 entries sampled; 3 titles confirmed against Notion |
| 6 — Markdown formatter | 23/23 unit tests, no Notion API needed |
| 7 — Block parser | **Human checkpoint** — sub-rows printed and spot-checked against live pages; sub-databases behind integration wall warned + skipped |
| 8 — CSV writer | 4/4 unit tests including Markdown round-trip with embedded commas/quotes/newlines |
| 9 — Orchestration | End-to-end: 7 entries, 55 sub-rows, 80% non-trivial; all structural assertions pass |
| 10 — Warning system | 3/3 unit tests: unknown block skips, missing property graceful, warnings stderr-only |
| — | Added `id`/`parent_id` columns (MD5-stable); heading accumulation |
| — | Added `last_edited_time (built-in)` and `created_time (built-in)` as date options |
| — | Fixed progress bar cursor drift on macOS (`\033[1B` vs `\n`) |

---

## Known Limitations and Future Work

- **Linked databases** (`child_page` blocks pointing to external databases) are not followed — they appear as `[WARN] unrecognised block type` and are skipped.
- **Toggle depth** is one level only. Nested toggles within toggles do not recurse.
- **Sub-databases not shared** with the integration produce `[WARN]` and are skipped. Each sub-database must be explicitly shared with the Notion integration in the Notion UI.
- **Image, file, video, embed blocks** are skipped with a warning. Only text-bearing block types are extracted.
- **Notion formula and rollup properties** are not available as date or people fields (the API does not expose their computed values in the properties filter).
- **Multiple person fields** are merged and deduplicated into one semicolon-separated cell. If downstream tooling needs them separated by source field, the CSV schema would need an additional column per field.
- **`--no-tui` flag** for non-interactive / scripted use is not yet implemented. Currently the curses TUI is always required to select fields.
