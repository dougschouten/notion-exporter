"""Task 9: End-to-end integration test — skips TUI, uses known field names."""
import csv, os, sys, tempfile
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

TOKEN = os.environ.get("NOTION_TOKEN", "")
DATABASE_ID = os.environ.get("NOTION_DB_ID", "15426c37bff781f9b6b5ead5af23a85f")
START_STR = "2024-01-01"
END_STR   = "2025-12-31"
DATE_FIELD    = "Dates"
PERSON_FIELDS = ["Owner", "Contributors"]


def run(client, output_path):
    from notion_exporter.database_fetcher import fetch_entries, parse_entry_properties
    from notion_exporter.page_parser import parse_page
    from notion_exporter.csv_writer import open_csv, write_parent_row, write_sub_row

    start = date.fromisoformat(START_STR)
    end   = date.fromisoformat(END_STR)

    entries = fetch_entries(client, DATABASE_ID, DATE_FIELD, START_STR, END_STR)
    assert entries, "No entries returned"
    print(f"Entries: {len(entries)}")

    f, writer = open_csv(output_path)
    entry_count = subitem_count = nontrivial_count = 0
    sub_db_cache = {}

    try:
        for i, entry in enumerate(entries, 1):
            parent = parse_entry_properties(entry, PERSON_FIELDS, DATE_FIELD)
            write_parent_row(writer, parent)
            entry_count += 1

            sub_rows = parse_page(
                client, entry["id"], start, end,
                sub_db_cache, lambda t, r, c: None, DATE_FIELD,
            )
            for sr in sub_rows:
                write_sub_row(writer, sr, parent["people"], parent["id"])
                subitem_count += 1
                if len(sr.get("technical_work_data", "")) > 50:
                    nontrivial_count += 1

            print(f"  Entry {i}: {parent['title']!r} → {len(sub_rows)} sub-rows")
    finally:
        f.close()

    # Assertions
    with open(output_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) > 0, "CSV is empty"
    entry_rows   = [r for r in rows if r["type"] == "entry"]
    subitem_rows = [r for r in rows if r["type"] == "subitem"]
    assert len(entry_rows) > 0, "No entry rows in CSV"
    assert len(subitem_rows) > 0, "No subitem rows in CSV"

    for r in rows:
        for col in ["type", "id", "parent_id", "title", "people", "date", "technical_work_data"]:
            assert col in r, f"Missing column {col!r}"

    for r in entry_rows:
        assert r["title"], f"Entry row missing title: {r}"
        assert r["id"],    f"Entry row missing id: {r}"
        assert r["parent_id"] == "", f"Entry row should have empty parent_id: {r}"

    for r in subitem_rows:
        assert r["parent_id"], f"Subitem row missing parent_id: {r}"
        assert r["id"] == "",  f"Subitem row should have empty id: {r}"

    if subitem_count:
        pct = 100 * nontrivial_count // subitem_count
        assert pct >= 20, f"Only {pct}% of subitems have non-trivial content (expected ≥20%)"

    print(f"\n── Summary ──")
    print(f"  Entry rows    : {len(entry_rows)}")
    print(f"  Subitem rows  : {len(subitem_rows)}")
    if subitem_count:
        print(f"  Non-trivial   : {nontrivial_count} ({pct}%)")
    print(f"  Output        : {output_path}")
    print(f"\nAll assertions passed.")
    print("\n── Human Checkpoint ──")
    print("Open the CSV in a spreadsheet app and spot-check 5 rows:")
    print("  • Parent entries match Notion database records")
    print("  • Subitems contain recognisable text from Notion pages")
    print("  • Markdown formatting is intact in technical_work_data")
    print("  • No columns are scrambled or truncated")


if __name__ == "__main__":
    from notion_exporter.notion_client import NotionClient
    client = NotionClient(TOKEN)
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as tmp:
        path = tmp.name
    print(f"Writing to: {path}")
    run(client, path)
    # Also write a readable copy next to the test
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       f"notion_export_{START_STR}_{END_STR}.csv")
    import shutil; shutil.copy(path, out)
    print(f"Copy saved to: {out}")
