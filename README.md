# notion-exporter

Export a Notion database to a structured CSV, including Markdown-formatted page content.

## Features

- Filter entries by any date property or built-in `last_edited_time` / `created_time`
- Interactive TUI to select person fields, date field, and any extra property columns
- Recursively parses page content: toggles, text blocks, headings, sub-databases
- Outputs a flat CSV with parent entry rows and child sub-rows linked by `id` / `parent_id`
- ANSI progress bar with ephemeral warnings during export

## Installation

```bash
pip install .
```

Requires Python ≥ 3.9 and a [Notion API integration token](https://www.notion.so/my-integrations).  
Share your database with the integration before running.

## Usage

```bash
notion-export <DATABASE_URL> --token <TOKEN> --start YYYY-MM-DD --end YYYY-MM-DD [--output FILE]
```

Or run directly without installing:

```bash
PYTHONPATH=src python3 -m notion_exporter.cli <DATABASE_URL> --token <TOKEN> --start YYYY-MM-DD --end YYYY-MM-DD
```

### Example

```bash
notion-export "https://www.notion.so/myworkspace/abc123..." \
  --token ntn_xxxxxxxxxxxx \
  --start 2024-01-01 \
  --end 2024-12-31
```

will produce something like

```bash
Database ID : abc123...
Date range  : 2025-01-01 → 2025-12-31
Output      : notion_export_2025-01-01_2025-12-31.csv

Fetching database metadata…

Person fields : Contributors
Date field    : created_time (built-in)
Extra columns : category, project
Querying database…
Found 800 entries.
800 entries · 9685 sub-items (53% non-trivial) → notion_export_2025-01-01_2025-12-31.csv
  ████████████████████████████████████████  100%  800/800 entries
  Entries     : 800
  Sub-items   : 9685
  Non-trivial : 5140 (53%)
  Output      : notion_export_2025-01-01_2025-12-31.csv
```

A TUI will prompt you to select:
1. **Person field(s)** — whose names appear in the `people` column
2. **Date field** — used to filter entries by the date range
3. **Extra columns** — any other database properties to include (optional, ESC to skip)

Output is saved to `notion_export_<start>_<end>.csv` by default.

## CSV Schema

| Column | Entry rows | Sub-item rows |
|--------|-----------|---------------|
| `type` | `entry` | `subitem` |
| `id` | 8-char stable hash | _(empty)_ |
| `parent_id` | _(empty)_ | parent entry `id` |
| `title` | DB entry title | Toggle/block heading |
| `people` | Semicolon-separated names | Inherited from parent |
| `date` | From selected date field | From block context |
| `technical_work_data` | _(empty)_ | Markdown-formatted block content |
| _extra columns_ | Value from selected property | _(empty)_ |

## Development

```bash
pip install -e .
python3 tests/test_task1_scaffolding.py
python3 tests/test_task6_formatter.py
python3 tests/test_task8_csv.py
python3 tests/test_task10_warnings.py
```
