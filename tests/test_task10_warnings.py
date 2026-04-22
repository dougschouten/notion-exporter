"""Task 10 tests: warning system — unknown blocks, missing properties, stderr isolation."""
import io, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from contextlib import redirect_stderr
from unittest.mock import MagicMock
from datetime import date


def _make_text_seg(text):
    return {"plain_text": text, "annotations": {
        "bold": False, "italic": False, "code": False,
        "strikethrough": False, "underline": False, "color": "default",
    }, "href": None}

def _make_block(btype, text="content", created="2024-03-01T00:00:00.000Z"):
    return {
        "type": btype, "id": f"block-{btype}",
        "created_time": created,
        btype: {"rich_text": [_make_text_seg(text)]},
    }


def test_unknown_block_warns_and_continues():
    from notion_exporter.page_parser import parse_page
    start = date(2024, 1, 1)
    end = date(2024, 12, 31)

    unknown_block = {"type": "synced_block", "id": "unk-1", "created_time": "2024-03-01T00:00:00.000Z", "synced_block": {}}
    good_block = _make_block("paragraph", "Good content")

    client = MagicMock()
    client.paginate_get.return_value = iter([unknown_block, good_block])

    buf = io.StringIO()
    with redirect_stderr(buf):
        rows = parse_page(client, "page-id", start, end, {}, lambda t, r, c: None, "Date")

    stderr_out = buf.getvalue()
    assert "[WARN]" in stderr_out, "Expected [WARN] in stderr"
    assert "synced_block" in stderr_out, "Expected block type in warning"
    assert len(rows) == 1, f"Expected 1 subrow from good block, got {len(rows)}"
    assert rows[0]["technical_work_data"] == "Good content"
    print("  PASS: unknown block type → warning + processing continues")


def test_missing_people_property_warns():
    from notion_exporter.database_fetcher import parse_entry_properties
    page = {
        "id": "page-abc",
        "properties": {
            "Name": {"type": "title", "title": [_make_text_seg("Entry A")]},
            "Date": {"type": "date", "date": {"start": "2024-03-01"}},
            # "Assignee" deliberately missing
        }
    }
    buf = io.StringIO()
    with redirect_stderr(buf):
        row = parse_entry_properties(page, ["Assignee"], "Date")

    assert "[WARN]" in buf.getvalue()
    assert row["title"] == "Entry A"
    assert row["people"] == []
    assert row["date"] == "2024-03-01"
    print("  PASS: missing people property → warning + empty people field + row produced")


def test_warnings_go_to_stderr_not_stdout():
    """Confirm [WARN] messages only appear on stderr, not stdout."""
    from notion_exporter.database_fetcher import parse_entry_properties
    page = {
        "id": "page-xyz",
        "properties": {
            "Name": {"type": "title", "title": [_make_text_seg("X")]},
        }
    }
    import io
    from contextlib import redirect_stdout
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
        parse_entry_properties(page, ["MissingPeople"], "MissingDate")

    assert "[WARN]" not in stdout_buf.getvalue(), "WARN leaked to stdout"
    assert "[WARN]" in stderr_buf.getvalue(), "WARN missing from stderr"
    print("  PASS: warnings only on stderr, stdout is clean")


if __name__ == "__main__":
    test_unknown_block_warns_and_continues()
    test_missing_people_property_warns()
    test_warnings_go_to_stderr_not_stdout()
    print("\nAll Task 10 warning system tests passed.")
