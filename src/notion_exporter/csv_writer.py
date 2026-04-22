import csv

FIELDNAMES = ["type", "id", "parent_id", "title", "people", "date", "technical_work_data"]


def open_csv(output_path):
    f = open(output_path, "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(f, fieldnames=FIELDNAMES, quoting=csv.QUOTE_ALL)
    writer.writeheader()
    return f, writer


def write_parent_row(writer, row):
    writer.writerow({
        "type": "entry",
        "id": row.get("id", ""),
        "parent_id": "",
        "title": row.get("title", ""),
        "people": ";".join(row.get("people", [])),
        "date": row.get("date", ""),
        "technical_work_data": "",
    })


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
