import argparse
import re
import sys
from dateutil.parser import parse as parse_date

from .notion_client import NotionClient
from .database_fetcher import (
    fetch_database_metadata,
    extract_typed_properties,
    extract_other_properties,
    fetch_entries,
    parse_entry_properties,
)
from .property_selector import single_select, multi_select
from .page_parser import parse_page
from .csv_writer import open_csv, write_parent_row, write_sub_row, auto_filename
from .progress import ProgressDisplay, ProgressStderr


def extract_database_id(url):
    clean = url.split("?")[0].split("#")[0].rstrip("/")
    segment = clean.split("/")[-1]
    match = re.search(r"([0-9a-f]{32})$", segment, re.IGNORECASE)
    if match:
        return match.group(1)
    if re.fullmatch(r"[0-9a-f]{32}", segment, re.IGNORECASE):
        return segment
    return segment


def main():
    parser = argparse.ArgumentParser(
        description="Export a Notion database to CSV, including page sub-content."
    )
    parser.add_argument("url", help="Notion database URL")
    parser.add_argument("--token", required=True, help="Notion API integration token")
    parser.add_argument("--start", required=True, help="Start date inclusive (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date inclusive (YYYY-MM-DD)")
    parser.add_argument("--output", help="Output CSV path (default: auto-generated from dates)")

    args = parser.parse_args()

    try:
        start = parse_date(args.start).date()
        end   = parse_date(args.end).date()
    except Exception as exc:
        print(f"Error: invalid date: {exc}", file=sys.stderr)
        sys.exit(1)

    if start > end:
        print(f"Error: start {start} is after end {end}", file=sys.stderr)
        sys.exit(1)

    database_id = extract_database_id(args.url)
    output_path = args.output or auto_filename(args.start, args.end)

    # Pre-TUI messages go directly to stderr (progress display not up yet)
    err = sys.stderr
    print(f"Database ID : {database_id}", file=err)
    print(f"Date range  : {start} → {end}", file=err)
    print(f"Output      : {output_path}", file=err)

    client = NotionClient(args.token)

    print("\nFetching database metadata…", file=err)
    properties = fetch_database_metadata(client, database_id)
    if not properties:
        print("Error: could not retrieve database properties. Check token and URL.", file=err)
        sys.exit(1)

    typed = extract_typed_properties(properties)

    if not typed["people"]:
        print("Error: no people-type properties found in database.", file=err)
        sys.exit(1)
    if not typed["date"]:
        print("Error: no date-type properties found in database.", file=err)
        sys.exit(1)

    # --- TUI: select person fields ---
    person_rows = [{"name": n} for n in sorted(typed["people"])]
    selected_people = multi_select(
        "Select person field(s) to include in CSV",
        person_rows,
        ["name"],
    )
    if not selected_people:
        print("Error: no person field selected, exiting.", file=err)
        sys.exit(1)
    person_fields = [r["name"] for r in selected_people]

    # --- TUI: select date field ---
    date_rows = [{"name": n} for n in sorted(typed["date"])]
    selected_date = single_select(
        "Select date field to filter database entries by",
        date_rows,
        ["name"],
    )
    if selected_date is None:
        print("Error: no date field selected, exiting.", file=err)
        sys.exit(1)
    date_field = selected_date["name"]

    # --- TUI: select extra property columns ---
    exclude_names = set(person_fields) | {date_field}
    other_props = extract_other_properties(properties, exclude_names)
    extra_fields = []  # list of (original_name, snake_col)
    if other_props:
        other_rows = [{"name": p["name"], "column": p["snake"], "type": p["type"]} for p in other_props]
        selected_extra = multi_select(
            "Select extra property columns to include (ESC to skip)",
            other_rows,
            ["name", "type", "column"],
            optional=True,
        )
        if selected_extra:
            extra_fields = [(r["name"], r["column"]) for r in selected_extra]

    print(f"\nPerson fields : {', '.join(person_fields)}", file=err)
    print(f"Date field    : {date_field}", file=err)
    if extra_fields:
        print(f"Extra columns : {', '.join(col for _, col in extra_fields)}", file=err)

    # --- Fetch entries (before installing progress display) ---
    print(f"Querying database…", file=err)
    entries = fetch_entries(client, database_id, date_field, args.start, args.end)
    print(f"Found {len(entries)} entries.", file=err)

    if not entries:
        print("No entries matched the date range. Exiting.", file=err)
        sys.exit(0)

    # --- Install progress display + stderr router ---
    display = ProgressDisplay(total=len(entries))
    real_stderr = sys.stderr
    sys.stderr = ProgressStderr(display)

    # --- Write CSV ---
    sub_db_date_cache = {}

    def selector_fn(title, rows, columns):
        # Temporarily restore real stderr so curses can run cleanly
        sys.stderr = real_stderr
        result = single_select(title, rows, columns)
        sys.stderr = ProgressStderr(display)
        return result

    extra_columns = [col for _, col in extra_fields]
    f, writer = open_csv(output_path, extra_columns)
    entry_count = subitem_count = nontrivial_count = 0

    try:
        for i, entry in enumerate(entries, 1):
            parent_row = parse_entry_properties(entry, person_fields, date_field, extra_fields)
            title_preview = parent_row["title"][:55] + "…" if len(parent_row["title"]) > 55 else parent_row["title"]
            display.update(i, title_preview)

            write_parent_row(writer, parent_row)
            entry_count += 1

            sub_rows = parse_page(
                client,
                entry["id"],
                start,
                end,
                sub_db_date_cache,
                selector_fn,
                date_field,
            )

            for sub_row in sub_rows:
                write_sub_row(writer, sub_row, parent_row["people"], parent_row["id"])
                subitem_count += 1
                if len(sub_row.get("technical_work_data", "")) > 50:
                    nontrivial_count += 1
    finally:
        f.close()
        sys.stderr = real_stderr

    nontrivial_pct = (100 * nontrivial_count // subitem_count) if subitem_count else 0
    display.finish(
        f"{entry_count} entries · {subitem_count} sub-items "
        f"({nontrivial_pct}% non-trivial) → {output_path}"
    )

    # Final summary to real stderr (below the progress footer)
    print(f"  Entries     : {entry_count}", file=real_stderr)
    print(f"  Sub-items   : {subitem_count}", file=real_stderr)
    if subitem_count:
        print(f"  Non-trivial : {nontrivial_count} ({nontrivial_pct}%)", file=real_stderr)
    print(f"  Output      : {output_path}", file=real_stderr)


if __name__ == "__main__":
    main()
