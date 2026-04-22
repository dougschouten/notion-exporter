import sys


def rich_text_to_markdown(rich_text_array):
    parts = []
    for segment in rich_text_array:
        text = segment.get("plain_text", "")
        ann = segment.get("annotations", {})
        href = segment.get("href")

        # Innermost annotation applied first so outer wrappers wrap it correctly.
        # Order: code > bold > italic > strikethrough
        if ann.get("code"):
            text = f"`{text}`"
        if ann.get("bold"):
            text = f"**{text}**"
        if ann.get("italic"):
            text = f"*{text}*"
        if ann.get("strikethrough"):
            text = f"~~{text}~~"

        if href:
            text = f"[{text}]({href})"

        parts.append(text)
    return "".join(parts)


def block_to_markdown(block):
    block_type = block.get("type", "")
    type_data = block.get(block_type, {})
    rich_text = type_data.get("rich_text")

    if rich_text is None:
        if block_type not in ("divider", "child_database", "child_page", "image", "file", "video"):
            print(
                f"[WARN] Block {block.get('id', '?')} (type: \"{block_type}\"): missing rich_text key",
                file=sys.stderr,
            )
        return ""

    content = rich_text_to_markdown(rich_text)

    if block_type == "heading_1":
        return f"# {content}"
    if block_type == "heading_2":
        return f"## {content}"
    if block_type == "heading_3":
        return f"### {content}"
    if block_type == "bulleted_list_item":
        return f"- {content}"
    if block_type == "numbered_list_item":
        return f"1. {content}"
    if block_type == "to_do":
        mark = "x" if type_data.get("checked") else " "
        return f"- [{mark}] {content}"
    if block_type == "quote":
        return f"> {content}"
    if block_type == "callout":
        icon_data = type_data.get("icon", {})
        emoji = ""
        if icon_data and icon_data.get("type") == "emoji":
            emoji = icon_data.get("emoji", "") + " "
        return f"> {emoji}{content}"
    if block_type == "code":
        language = type_data.get("language", "")
        return f"```{language}\n{content}\n```"
    # paragraph and any other text-bearing type
    return content
