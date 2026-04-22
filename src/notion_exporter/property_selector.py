import curses
import sys


def _col_widths(rows, columns):
    widths = {}
    for col in columns:
        header_len = len(col)
        max_val_len = max((len(str(r.get(col, ""))) for r in rows), default=0)
        widths[col] = min(max(header_len, max_val_len), 50)
    return widths


def _draw_table(stdscr, title, rows, columns, selected_indices, current_row, multi, error_msg=""):
    stdscr.clear()
    height, width = stdscr.getmaxyx()

    def safe_addstr(y, x, text, attr=curses.A_NORMAL):
        if y >= height - 1 or x >= width - 1:
            return
        text = text[: width - 1 - x]
        try:
            stdscr.addstr(y, x, text, attr)
        except curses.error:
            pass

    # Title bar
    safe_addstr(0, 0, f" {title} ", curses.A_BOLD | curses.A_REVERSE)

    # Instructions
    if multi:
        inst = "  ↑/↓ Navigate   Space: Toggle   Enter: Confirm   Esc: Cancel"
    else:
        inst = "  ↑/↓ Navigate   Enter: Confirm   Esc: Cancel"
    safe_addstr(1, 0, inst, curses.A_DIM)

    col_w = _col_widths(rows, columns)
    check_w = 4 if multi else 0  # "[x] " prefix

    # Build total row width for background fill
    total_w = check_w + sum(col_w[c] + 2 for c in columns)

    # Column header row (y=3)
    header_y = 3
    row_str = (" " * check_w) + "  ".join(c.upper().ljust(col_w[c]) for c in columns)
    safe_addstr(header_y, 0, row_str[: width - 1], curses.A_REVERSE | curses.A_BOLD)

    # Separator (y=4)
    sep_y = header_y + 1
    safe_addstr(sep_y, 0, "─" * min(total_w, width - 1))

    # Scrollable data rows start at y=5
    data_start_y = sep_y + 1
    max_visible = height - data_start_y - 2  # leave room for error line

    # Scroll window: keep current_row visible
    scroll_offset = max(0, current_row - max_visible + 1)

    for vis_i, row_i in enumerate(range(scroll_offset, min(scroll_offset + max_visible, len(rows)))):
        y = data_start_y + vis_i
        row = rows[row_i]
        is_current = row_i == current_row

        prefix = ""
        if multi:
            prefix = "[x] " if row_i in selected_indices else "[ ] "

        cells = "  ".join(str(row.get(c, "")).ljust(col_w[c])[: col_w[c]] for c in columns)
        line = (prefix + cells)[: width - 1]

        attr = curses.A_REVERSE if is_current else curses.A_NORMAL
        safe_addstr(y, 0, line.ljust(min(total_w, width - 1)), attr)

    # Error / status line at bottom
    if error_msg:
        safe_addstr(height - 2, 0, f"  {error_msg}", curses.A_BOLD)

    stdscr.refresh()


def single_select(title, rows, columns):
    if not rows:
        print(f"[WARN] single_select: no options available for \"{title}\"", file=sys.stderr)
        return None

    result = [None]

    def _run(stdscr):
        curses.curs_set(0)
        current_row = 0
        while True:
            _draw_table(stdscr, title, rows, columns, set(), current_row, multi=False)
            key = stdscr.getch()
            if key == curses.KEY_UP:
                current_row = max(0, current_row - 1)
            elif key == curses.KEY_DOWN:
                current_row = min(len(rows) - 1, current_row + 1)
            elif key in (curses.KEY_ENTER, 10, 13):
                result[0] = rows[current_row]
                break
            elif key == 27:  # ESC
                break

    curses.wrapper(_run)
    if result[0] is None:
        print(f"[WARN] Selection cancelled for \"{title}\"", file=sys.stderr)
    return result[0]


def multi_select(title, rows, columns, optional=False):
    """Multi-select TUI. If optional=True, ESC returns [] without a warning."""
    if not rows:
        return []

    result = [None]

    def _run(stdscr):
        curses.curs_set(0)
        current_row = 0
        selected = set()
        error_msg = ""
        while True:
            _draw_table(stdscr, title, rows, columns, selected, current_row, multi=True, error_msg=error_msg)
            key = stdscr.getch()
            error_msg = ""
            if key == curses.KEY_UP:
                current_row = max(0, current_row - 1)
            elif key == curses.KEY_DOWN:
                current_row = min(len(rows) - 1, current_row + 1)
            elif key == ord(" "):
                if current_row in selected:
                    selected.remove(current_row)
                else:
                    selected.add(current_row)
            elif key in (curses.KEY_ENTER, 10, 13):
                if not selected and not optional:
                    error_msg = "Please select at least one option (Space to toggle)."
                else:
                    result[0] = [rows[i] for i in sorted(selected)]
                    break
            elif key == 27:  # ESC
                result[0] = []
                break

    curses.wrapper(_run)
    if result[0] is None:
        if not optional:
            print(f"[WARN] Selection cancelled for \"{title}\"", file=sys.stderr)
        return []
    return result[0]
