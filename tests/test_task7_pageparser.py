"""Task 7: Page block parser — sub-row extraction + human checkpoint."""
import os, sys
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

TOKEN = os.environ.get("NOTION_TOKEN", "")
DATABASE_ID = os.environ.get("NOTION_DB_ID", "15426c37bff781f9b6b5ead5af23a85f")
START_STR = os.environ.get("NOTION_START", "2024-01-01")
END_STR   = os.environ.get("NOTION_END",   "2025-12-31")
DATE_FIELD   = os.environ.get("NOTION_DATE_FIELD", "Dates")
PERSON_FIELDS = os.environ.get("NOTION_PERSON_FIELDS", "Owner,Contributors").split(",")


def run(client):
    from notion_exporter.database_fetcher import fetch_entries, parse_entry_properties
    from notion_exporter.page_parser import parse_page

    start = date.fromisoformat(START_STR)
    end   = date.fromisoformat(END_STR)

    entries = fetch_entries(client, DATABASE_ID, DATE_FIELD, START_STR, END_STR)
    assert entries, "No entries returned"

    all_sub_rows = []
    print(f"\nParsing first 3 of {len(entries)} entries...\n")

    for entry in entries[:3]:
        parent = parse_entry_properties(entry, PERSON_FIELDS, DATE_FIELD)
        print(f"{'='*60}")
        print(f"ENTRY : {parent['title']}")
        print(f"People: {', '.join(parent['people']) or '(none)'}")
        print(f"Date  : {parent['date']}")
        print()

        sub_rows = parse_page(client, entry["id"], start, end, {}, lambda t, r, c: None, DATE_FIELD)
        print(f"  Sub-rows found: {len(sub_rows)}")
        for sr in sub_rows:
            preview = sr["technical_work_data"][:200].replace("\n", "↵")
            print(f"  [{sr['date']}] title={sr['title']!r:30s}  data={preview!r}")
        all_sub_rows.extend(sub_rows)
        print()

    # Automated assertions
    assert any(sr["technical_work_data"] for sr in all_sub_rows), \
        "No sub-rows had any technical_work_data"
    for sr in all_sub_rows:
        sr_date = date.fromisoformat(sr["date"]) if sr["date"] else None
        if sr_date:
            assert start <= sr_date <= end, f"Sub-row date {sr_date} out of range"

    non_trivial = sum(1 for sr in all_sub_rows if len(sr["technical_work_data"]) > 50)
    print(f"Assertions passed.")
    print(f"Total sub-rows: {len(all_sub_rows)}, non-trivial (>50 chars): {non_trivial}")
    print("\n── Human Checkpoint ──")
    print("Open one of the above Notion pages and verify:")
    print("  • Toggle titles match those shown above")
    print("  • Toggle body text is present and Markdown-formatted")
    print("  • Top-level text blocks appear as sub-rows with empty title")
    print("  • Sub-database entries in range are included")
    print("  • Entries outside the date range are absent")


if __name__ == "__main__":
    from notion_exporter.notion_client import NotionClient
    client = NotionClient(TOKEN)
    run(client)
    print("\nTask 7 complete.")
