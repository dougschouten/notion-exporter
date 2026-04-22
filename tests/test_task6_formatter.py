"""Task 6 unit tests: rich_text → Markdown conversion (no Notion API needed)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from notion_exporter.text_formatter import rich_text_to_markdown, block_to_markdown


def make_seg(text, bold=False, italic=False, code=False, strikethrough=False, href=None):
    return {
        "plain_text": text,
        "annotations": {
            "bold": bold, "italic": italic, "code": code,
            "strikethrough": strikethrough, "underline": False, "color": "default",
        },
        "href": href,
    }


def test_plain():
    assert rich_text_to_markdown([make_seg("hello")]) == "hello"
    print("  PASS: plain text")

def test_bold():
    assert rich_text_to_markdown([make_seg("hi", bold=True)]) == "**hi**"
    print("  PASS: bold")

def test_italic():
    assert rich_text_to_markdown([make_seg("hi", italic=True)]) == "*hi*"
    print("  PASS: italic")

def test_code_inline():
    assert rich_text_to_markdown([make_seg("x", code=True)]) == "`x`"
    print("  PASS: inline code")

def test_strikethrough():
    assert rich_text_to_markdown([make_seg("del", strikethrough=True)]) == "~~del~~"
    print("  PASS: strikethrough")

def test_bold_italic():
    # bold wraps italic wraps text; code not set so order is bold > italic
    result = rich_text_to_markdown([make_seg("x", bold=True, italic=True)])
    assert result == "***x***", f"Got: {result!r}"
    print("  PASS: bold+italic")

def test_code_bold():
    # code applied first (innermost), then bold wraps it
    result = rich_text_to_markdown([make_seg("x", code=True, bold=True)])
    assert result == "**`x`**", f"Got: {result!r}"
    print("  PASS: code+bold")

def test_link():
    result = rich_text_to_markdown([make_seg("Notion", href="https://notion.so")])
    assert result == "[Notion](https://notion.so)", f"Got: {result!r}"
    print("  PASS: link")

def test_link_with_bold():
    result = rich_text_to_markdown([make_seg("Bold link", bold=True, href="https://notion.so")])
    assert result == "[**Bold link**](https://notion.so)", f"Got: {result!r}"
    print("  PASS: bold link")

def test_empty_rich_text():
    assert rich_text_to_markdown([]) == ""
    print("  PASS: empty rich_text → empty string")

def test_multiple_segments():
    segs = [make_seg("Hello "), make_seg("world", bold=True)]
    assert rich_text_to_markdown(segs) == "Hello **world**"
    print("  PASS: multiple segments")

# block_to_markdown tests

def make_block(block_type, rich_text, **extras):
    b = {"type": block_type, "id": "test-id", block_type: {"rich_text": rich_text}}
    b[block_type].update(extras)
    return b

def test_heading1():
    b = make_block("heading_1", [make_seg("Title")])
    assert block_to_markdown(b) == "# Title"
    print("  PASS: heading_1")

def test_heading2():
    b = make_block("heading_2", [make_seg("Sub")])
    assert block_to_markdown(b) == "## Sub"
    print("  PASS: heading_2")

def test_heading3():
    b = make_block("heading_3", [make_seg("Sub")])
    assert block_to_markdown(b) == "### Sub"
    print("  PASS: heading_3")

def test_bullet():
    b = make_block("bulleted_list_item", [make_seg("item")])
    assert block_to_markdown(b) == "- item"
    print("  PASS: bullet")

def test_numbered():
    b = make_block("numbered_list_item", [make_seg("item")])
    assert block_to_markdown(b) == "1. item"
    print("  PASS: numbered_list_item")

def test_todo_unchecked():
    b = make_block("to_do", [make_seg("task")], checked=False)
    assert block_to_markdown(b) == "- [ ] task"
    print("  PASS: to_do unchecked")

def test_todo_checked():
    b = make_block("to_do", [make_seg("done")], checked=True)
    assert block_to_markdown(b) == "- [x] done"
    print("  PASS: to_do checked")

def test_quote():
    b = make_block("quote", [make_seg("wise words")])
    assert block_to_markdown(b) == "> wise words"
    print("  PASS: quote")

def test_code_block():
    b = make_block("code", [make_seg("print('hi')")], language="python")
    assert block_to_markdown(b) == "```python\nprint('hi')\n```"
    print("  PASS: code block")

def test_paragraph():
    b = make_block("paragraph", [make_seg("Some text")])
    assert block_to_markdown(b) == "Some text"
    print("  PASS: paragraph")

def test_missing_rich_text(capsys=None):
    b = {"type": "paragraph", "id": "x", "paragraph": {}}
    import io
    from contextlib import redirect_stderr
    buf = io.StringIO()
    with redirect_stderr(buf):
        result = block_to_markdown(b)
    assert result == ""
    assert "[WARN]" in buf.getvalue()
    print("  PASS: missing rich_text → empty + warning")

def test_empty_rich_text_block():
    b = make_block("paragraph", [])
    assert block_to_markdown(b) == ""
    print("  PASS: empty rich_text list → empty string")


if __name__ == "__main__":
    tests = [
        test_plain, test_bold, test_italic, test_code_inline, test_strikethrough,
        test_bold_italic, test_code_bold, test_link, test_link_with_bold,
        test_empty_rich_text, test_multiple_segments,
        test_heading1, test_heading2, test_heading3,
        test_bullet, test_numbered, test_todo_unchecked, test_todo_checked,
        test_quote, test_code_block, test_paragraph,
        test_missing_rich_text, test_empty_rich_text_block,
    ]
    for t in tests:
        t()
    print(f"\nAll {len(tests)} Task 6 formatter tests passed.")
