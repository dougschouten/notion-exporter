"""Task 8 tests: CSV writer — round-trip, quoting, filename generation, id/parent_id."""
import csv, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from notion_exporter.csv_writer import open_csv, write_parent_row, write_sub_row, auto_filename, FIELDNAMES


def test_round_trip():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
        path = tmp.name

    try:
        f, writer = open_csv(path)
        parent1 = {"id": "AABB1122", "type": "entry", "title": "Work item A", "people": ["Alice", "Bob"], "date": "2024-03-01", "technical_work_data": ""}
        parent2 = {"id": "CCDD3344", "type": "entry", "title": "Work item B", "people": ["Carol"],        "date": "2024-03-15", "technical_work_data": ""}
        write_parent_row(writer, parent1)
        write_sub_row(writer, {"title": "Toggle header", "date": "2024-03-01", "technical_work_data": "Some work done"}, parent1["people"], parent1["id"])
        write_sub_row(writer, {"title": "",              "date": "2024-03-02", "technical_work_data": "More work"},      parent1["people"], parent1["id"])
        write_parent_row(writer, parent2)
        write_sub_row(writer, {"title": "DB page",       "date": "2024-03-15", "technical_work_data": "Implemented X"}, parent2["people"], parent2["id"])
        write_sub_row(writer, {"title": "",              "date": "2024-03-16", "technical_work_data": "Fixed Y"},        parent2["people"], parent2["id"])
        f.close()

        with open(path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))

        assert len(rows) == 6, f"Expected 6 rows, got {len(rows)}"
        assert rows[0]["type"] == "entry"
        assert rows[1]["type"] == "subitem"
        assert rows[0]["people"] == "Alice;Bob"
        assert rows[3]["people"] == "Carol"
        # id / parent_id linkage
        assert rows[0]["id"] == "AABB1122"
        assert rows[0]["parent_id"] == ""
        assert rows[1]["parent_id"] == "AABB1122"
        assert rows[1]["id"] == ""
        assert rows[3]["id"] == "CCDD3344"
        assert rows[4]["parent_id"] == "CCDD3344"
        # All columns present in every row
        for row in rows:
            for col in FIELDNAMES:
                assert col in row, f"Missing column {col!r} in row {row}"
        print("  PASS: round-trip, id/parent_id linkage, column presence")
    finally:
        os.unlink(path)


def test_markdown_quoting():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
        path = tmp.name
    try:
        f, writer = open_csv(path)
        markdown = '## Title\n- item one, "quoted"\n- item two\n```python\nprint("hi")\n```'
        write_sub_row(writer, {
            "title": "My toggle",
            "date": "2024-01-01", "technical_work_data": markdown,
        }, ["Alice"], "AABB1122")
        f.close()

        with open(path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))

        assert rows[0]["technical_work_data"] == markdown, \
            f"Markdown corrupted.\nExpected: {markdown!r}\nGot:      {rows[0]['technical_work_data']!r}"
        print("  PASS: Markdown with commas/quotes/newlines survives round-trip")
    finally:
        os.unlink(path)


def test_auto_filename():
    name = auto_filename("2024-01-01", "2024-03-31")
    assert name == "notion_export_2024-01-01_2024-03-31.csv", f"Got: {name!r}"
    print("  PASS: auto-generated filename")


def test_parent_technical_work_data_empty():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
        path = tmp.name
    try:
        f, writer = open_csv(path)
        parent = {"id": "ZZXX9900", "type": "entry", "title": "P", "people": ["X"], "date": "2024-01-01", "technical_work_data": ""}
        write_parent_row(writer, parent)
        write_sub_row(writer, {"title": "", "date": "2024-01-01", "technical_work_data": "Real content here"}, ["X"], "ZZXX9900")
        f.close()

        with open(path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))

        assert rows[0]["technical_work_data"] == ""
        assert rows[1]["technical_work_data"] == "Real content here"
        print("  PASS: parent row has empty technical_work_data, subitem has content")
    finally:
        os.unlink(path)


if __name__ == "__main__":
    test_round_trip()
    test_markdown_quoting()
    test_auto_filename()
    test_parent_technical_work_data_empty()
    print("\nAll Task 8 CSV writer tests passed.")
