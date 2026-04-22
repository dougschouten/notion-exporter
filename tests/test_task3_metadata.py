"""Task 3: Database metadata fetch + property type extraction. Prints human checkpoint table."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

TOKEN = os.environ.get("NOTION_TOKEN", "")
DATABASE_ID = os.environ.get("NOTION_DB_ID", "15426c37bff781f9b6b5ead5af23a85f")


def test_metadata(client):
    from notion_exporter.database_fetcher import fetch_database_metadata, extract_typed_properties

    props = fetch_database_metadata(client, DATABASE_ID)
    assert props, "fetch_database_metadata returned empty — check token/DB ID"

    typed = extract_typed_properties(props)
    assert typed["date"], "No date-type properties found"
    assert typed["people"], "No people-type properties found"

    # Human checkpoint: print all properties as a formatted table
    col_w = {"name": max(4, max(len(k) for k in props)), "type": 20}
    sep = f"+{'-'*(col_w['name']+2)}+{'-'*(col_w['type']+2)}+"
    header = f"| {'NAME'.ljust(col_w['name'])} | {'TYPE'.ljust(col_w['type'])} |"
    print("\n── Human Checkpoint: All database properties ──")
    print(sep)
    print(header)
    print(sep)
    for name, prop in sorted(props.items()):
        t = prop.get("type", "?")
        marker = " ◀ date" if t == "date" else (" ◀ people" if t == "people" else "")
        print(f"| {name.ljust(col_w['name'])} | {(t + marker).ljust(col_w['type'])} |")
    print(sep)

    print(f"\nDate properties   : {typed['date']}")
    print(f"People properties : {typed['people']}")
    print("\nPlease verify that the above date and people fields match what you see in Notion.")


if __name__ == "__main__":
    from notion_exporter.notion_client import NotionClient
    client = NotionClient(TOKEN)
    test_metadata(client)
    print("\nTask 3 complete.")
