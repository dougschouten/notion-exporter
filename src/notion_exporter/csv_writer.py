import csv

BASE_FIELDNAMES = ["type", "id", "parent_id", "title", "people", "date", "technical_work_data"]
FIELDNAMES = BASE_FIELDNAMES  # backward-compat alias


def open_csv(output_path, extra_columns=None):
    fieldnames = BASE_FIELDNAMES + list(extra_columns or [])
    f = open(output_path, "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(
        f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL,
        extrasaction="ignore", restval="",
    )
    writer.writeheader()
    return f, writer


def write_parent_row(writer, row):
    d = {
        "type": "entry",
        "id": row.get("id", ""),
        "parent_id": "",
        "title": row.get("title", ""),
        "people": ";".join(row.get("people", [])),
        "date": row.get("date", ""),
        "technical_work_data": "",
    }
    # Merge any extra snake_case keys from the row dict
    for key, val in row.items():
        if key not in d:
            d[key] = val
    writer.writerow(d)


def write_sub_row(writer, sub_row, people, parent_id):
    writer.writerow({
        "type": "subitem",
        "id": "",
        "parent_id": parent_id,
        "title": sub_row.get("title", ""),
        "people": ";".join(people),
        "date": sub_row.get("date", ""),
        "technical_work_data": sub_row.get("technical_work_data", ""),
    })


def auto_filename(start_str, end_str):
    return f"notion_export_{start_str}_{end_str}.csv"
