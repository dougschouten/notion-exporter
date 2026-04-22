"""Task 5: Fetch and parse database entries. Prints 3-entry human checkpoint sample."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

TOKEN = os.environ.get("NOTION_TOKEN", "")
DATABASE_ID = os.environ.get("NOTION_DB_ID", "15426c37bff781f9b6b5ead5af23a85f")
START = os.environ.get("NOTION_START", "2024-01-01")
END   = os.environ.get("NOTION_END",   "2025-12-31")
DATE_FIELD   = os.environ.get("NOTION_DATE_FIELD",   "Dates")
PERSON_FIELDS = os.environ.get("NOTION_PERSON_FIELDS", "Owner").split(",")


def test_entries(client):
    from notion_exporter.database_fetcher import fetch_entries, parse_entry_properties

    entries = fetch_entries(client, DATABASE_ID, DATE_FIELD, START, END)
    assert len(entries) > 0, f"No entries returned for range {START}→{END}"
    print(f"\nTotal entries in range: {len(entries)}")

    # Validate every parsed entry
    bad = []
    for e in entries:
        row = parse_entry_properties(e, PERSON_FIELDS, DATE_FIELD)
        if not row["title"]:
            bad.append(f"  missing title: page {e['id']}")
        if not row["date"]:
            bad.append(f"  missing date: page {e['id']}")
    if bad:
        print("WARNINGS during parsing:")
        for b in bad:
            print(b)

    # Human checkpoint: print 3 sample entries
    print("\n── Human Checkpoint: 3 sample entries ──")
    for e in entries[:3]:
        row = parse_entry_properties(e, PERSON_FIELDS, DATE_FIELD)
        print(f"  Title  : {row['title']}")
        print(f"  People : {', '.join(row['people']) or '(none)'}")
        print(f"  Date   : {row['date']}")
        print()

    print("Verify these entries correspond to real records in Notion with correct people/date values.")


if __name__ == "__main__":
    from notion_exporter.notion_client import NotionClient
    client = NotionClient(TOKEN)
    test_entries(client)
    print("Task 5 complete.")
