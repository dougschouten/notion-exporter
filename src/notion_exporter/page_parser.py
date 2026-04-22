import sys
from datetime import timezone
from dateutil.parser import parse as parse_date

from .text_formatter import rich_text_to_markdown, block_to_markdown
from .database_fetcher import fetch_database_metadata, extract_typed_properties, fetch_entries

HEADING_TYPES = {"heading_1", "heading_2", "heading_3"}

# Text block types that produce sub-rows (headings excluded — they are accumulated)
TEXT_BLOCK_TYPES = {
    "paragraph",
    "bulleted_list_item",
    "numbered_list_item",
    "code",
    "quote",
    "callout",
    "to_do",
}

ALL_TEXT_TYPES = TEXT_BLOCK_TYPES | HEADING_TYPES


def _in_range(dt_str, start, end):
    if not dt_str:
        return False
    try:
        dt = parse_date(dt_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return start <= dt.date() <= end
    except Exception:
        return False


def _date_prefix(dt_str):
    return dt_str[:10] if dt_str else ""


def _flush_headings(pending_headings, next_text, next_date):
    """Combine accumulated heading lines with next_text into one sub-row."""
    heading_block = "\n".join(pending_headings)
    combined = f"{heading_block}\n\n{next_text}" if next_text else heading_block
    return {
        "type": "subitem",
        "title": "",
        "date": next_date,
        "technical_work_data": combined,
    }


def handle_text_block(block, start, end, pending_headings):
    """
    Handle a non-heading text block. If there are pending headings, prepend them
    to this block's content. Returns (sub_row | None, cleared_pending_headings).
    """
    created = block.get("created_time", "")
    if not _in_range(created, start, end):
        return None, pending_headings

    text = block_to_markdown(block)
    if not text and not pending_headings:
        return None, pending_headings

    row = _flush_headings(pending_headings, text, _date_prefix(created)) \
        if pending_headings else {
            "type": "subitem",
            "title": "",
            "date": _date_prefix(created),
            "technical_work_data": text,
        }
    return row, []


def handle_toggle(client, block, start, end, pending_headings):
    """
    Handle a toggle block. Pending headings are prepended to the toggle body.
    Returns (list[sub_row], cleared_pending_headings).
    """
    created = block.get("created_time", "")
    if not _in_range(created, start, end):
        return [], pending_headings

    toggle_data = block.get("toggle", {})
    title = rich_text_to_markdown(toggle_data.get("rich_text", []))

    try:
        children = list(client.paginate_get(f"/blocks/{block['id']}/children"))
    except Exception as exc:
        print(f"[WARN] Toggle {block.get('id', '?')}: failed to fetch children: {exc}", file=sys.stderr)
        children = []

    child_texts = []
    for child in children:
        child_type = child.get("type", "")
        if child_type in ALL_TEXT_TYPES:
            text = block_to_markdown(child)
            if text:
                child_texts.append(text)

    body = "\n".join(child_texts)
    if pending_headings:
        heading_block = "\n".join(pending_headings)
        body = f"{heading_block}\n\n{body}" if body else heading_block

    return [{
        "type": "subitem",
        "title": title,
        "date": _date_prefix(created),
        "technical_work_data": body,
    }], []


def handle_child_database(client, block, start, end, sub_db_date_cache, selector_fn, parent_date_field):
    db_id = block.get("id", "")

    if db_id in sub_db_date_cache:
        date_field = sub_db_date_cache[db_id]
    else:
        metadata = fetch_database_metadata(client, db_id)
        typed = extract_typed_properties(metadata)
        date_fields = typed.get("date", [])

        if not date_fields:
            print(f"[WARN] Sub-database {db_id}: no date-type properties found, skipping", file=sys.stderr)
            sub_db_date_cache[db_id] = None
            return []

        if parent_date_field in date_fields:
            date_field = parent_date_field
        else:
            db_title = block.get("child_database", {}).get("title", db_id)
            rows = [{"name": f} for f in date_fields]
            selected = selector_fn(
                f"Sub-database \"{db_title}\": select date field",
                rows,
                ["name"],
            )
            if selected is None:
                sub_db_date_cache[db_id] = None
                return []
            date_field = selected["name"]

        sub_db_date_cache[db_id] = date_field

    if date_field is None:
        return []

    try:
        entries = fetch_entries(client, db_id, date_field, start.isoformat(), end.isoformat())
    except Exception as exc:
        print(f"[WARN] Sub-database {db_id}: failed to fetch entries: {exc}", file=sys.stderr)
        return []

    sub_rows = []
    for page in entries:
        page_id = page.get("id", "?")

        title = ""
        for prop_data in page.get("properties", {}).values():
            if prop_data.get("type") == "title":
                title = "".join(seg.get("plain_text", "") for seg in prop_data.get("title", []))
                break

        try:
            blocks = list(client.paginate_get(f"/blocks/{page_id}/children"))
        except Exception as exc:
            print(f"[WARN] Sub-database page {page_id}: failed to fetch blocks: {exc}", file=sys.stderr)
            blocks = []

        texts = []
        for b in blocks:
            if b.get("type", "") in ALL_TEXT_TYPES:
                text = block_to_markdown(b)
                if text:
                    texts.append(text)

        sub_rows.append({
            "type": "subitem",
            "title": title,
            "date": _date_prefix(page.get("created_time", "")),
            "technical_work_data": "\n".join(texts),
        })

    return sub_rows


def parse_page(client, page_id, start, end, sub_db_date_cache, selector_fn, parent_date_field):
    try:
        blocks = list(client.paginate_get(f"/blocks/{page_id}/children"))
    except Exception as exc:
        print(f"[WARN] Page {page_id}: failed to fetch blocks: {exc}", file=sys.stderr)
        return []

    sub_rows = []
    pending_headings = []  # Heading Markdown lines waiting for the next non-heading block

    for block in blocks:
        block_type = block.get("type", "")
        block_id = block.get("id", "?")
        try:
            if block_type in HEADING_TYPES:
                # Accumulate heading; don't emit a sub-row yet
                created = block.get("created_time", "")
                if _in_range(created, start, end):
                    heading_md = block_to_markdown(block)
                    if heading_md:
                        pending_headings.append(heading_md)

            elif block_type in TEXT_BLOCK_TYPES:
                row, pending_headings = handle_text_block(block, start, end, pending_headings)
                if row:
                    sub_rows.append(row)

            elif block_type == "toggle":
                rows, pending_headings = handle_toggle(client, block, start, end, pending_headings)
                sub_rows.extend(rows)

            elif block_type == "child_database":
                # Flush any pending headings as a standalone sub-row before DB items
                if pending_headings:
                    created = block.get("created_time", "")
                    sub_rows.append(_flush_headings(pending_headings, "", _date_prefix(created)))
                    pending_headings = []
                sub_rows.extend(handle_child_database(
                    client, block, start, end,
                    sub_db_date_cache, selector_fn, parent_date_field,
                ))

            else:
                print(
                    f"[WARN] Block {block_id} (type: \"{block_type}\"): unrecognised block type, skipping",
                    file=sys.stderr,
                )
        except Exception as exc:
            print(
                f"[WARN] Block {block_id} (type: \"{block_type}\"): error during processing: {exc}",
                file=sys.stderr,
            )

    # Flush any headings remaining at end of page
    if pending_headings:
        sub_rows.append(_flush_headings(pending_headings, "", ""))

    return sub_rows
