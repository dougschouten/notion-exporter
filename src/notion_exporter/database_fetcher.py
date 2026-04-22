import sys

# Sentinel names for Notion built-in timestamps (not user-defined properties).
BUILTIN_LAST_EDITED = "last_edited_time (built-in)"
BUILTIN_CREATED     = "created_time (built-in)"

BUILTIN_TIMESTAMPS = {
    BUILTIN_LAST_EDITED: "last_edited_time",
    BUILTIN_CREATED:     "created_time",
}


def fetch_database_metadata(client, database_id):
    data = client.get(f"/databases/{database_id}")
    if data is None:
        print(f"[WARN] Could not fetch metadata for database {database_id}", file=sys.stderr)
        return {}
    return data.get("properties", {})


def extract_typed_properties(properties):
    result = {"date": [], "people": []}
    for name, prop in properties.items():
        t = prop.get("type")
        if t == "date":
            result["date"].append(name)
        elif t == "people":
            result["people"].append(name)

    # Always offer built-in timestamps as date options
    result["date"].append(BUILTIN_LAST_EDITED)
    result["date"].append(BUILTIN_CREATED)

    if not result["people"]:
        print("[WARN] No people-type properties found in database", file=sys.stderr)
    return result


def _build_date_filter(date_field, start_str, end_str):
    """Return a Notion filter dict for the given date field and range."""
    if date_field in BUILTIN_TIMESTAMPS:
        ts_key = BUILTIN_TIMESTAMPS[date_field]
        return {
            "and": [
                {"timestamp": ts_key, ts_key: {"on_or_after": start_str}},
                {"timestamp": ts_key, ts_key: {"on_or_before": end_str}},
            ]
        }
    return {
        "and": [
            {"property": date_field, "date": {"on_or_after": start_str}},
            {"property": date_field, "date": {"on_or_before": end_str}},
        ]
    }


def fetch_entries(client, database_id, date_field, start_str, end_str):
    body = {"filter": _build_date_filter(date_field, start_str, end_str)}
    return list(client.paginate_post(f"/databases/{database_id}/query", body))


def parse_entry_properties(page, person_fields, date_field):
    import hashlib
    props = page.get("properties", {})
    page_id = page.get("id", "?")

    # Stable 8-char ID derived from the Notion page UUID
    raw_id = page_id.replace("-", "")
    item_id = hashlib.md5(raw_id.encode()).hexdigest()[:8].upper()

    # Title — find the property with type == "title"
    title = ""
    for prop_data in props.values():
        if prop_data.get("type") == "title":
            title = "".join(seg.get("plain_text", "") for seg in prop_data.get("title", []))
            break

    # People — merge across all selected person fields, preserving order, deduplicating
    seen = set()
    unique_people = []
    for field in person_fields:
        if field not in props:
            print(f"[WARN] Page {page_id}, property \"{field}\": not found", file=sys.stderr)
            continue
        prop = props[field]
        if prop.get("type") != "people":
            print(f"[WARN] Page {page_id}, property \"{field}\": unexpected type {prop.get('type')}", file=sys.stderr)
            continue
        for person in prop.get("people", []):
            name = person.get("name") or person.get("id", "unknown")
            if name not in seen:
                seen.add(name)
                unique_people.append(name)

    # Date — built-in timestamp or user property
    date_str = ""
    if date_field in BUILTIN_TIMESTAMPS:
        ts_key = BUILTIN_TIMESTAMPS[date_field]
        raw_ts = page.get(ts_key, "")
        date_str = raw_ts[:10] if raw_ts else ""
    elif date_field not in props:
        print(f"[WARN] Page {page_id}, property \"{date_field}\": not found", file=sys.stderr)
    else:
        date_prop = props[date_field]
        date_val = date_prop.get("date") if date_prop.get("type") == "date" else None
        if not date_val:
            print(f"[WARN] Page {page_id}, property \"{date_field}\": null or missing date value", file=sys.stderr)
        else:
            date_str = date_val.get("start", "")

    return {
        "type": "entry",
        "id": item_id,
        "title": title,
        "people": unique_people,
        "date": date_str,
        "technical_work_data": "",
    }
