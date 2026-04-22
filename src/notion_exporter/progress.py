"""
Terminal progress display with ephemeral status/warning messages and a colour bar.
Falls back to plain line-by-line output when stderr is not a TTY.

Cursor accounting
-----------------
_ensure_ready() prints two bare newlines, leaving the cursor at line N+2.
Each _render() call:
  1. \033[2A\r       — move up 2, go to col 0  → line N
  2. \033[2K         — clear line N
  3. write message   — cursor still on line N
  4. \n\r\033[2K     — move to line N+1, col 0, clear it
  5. write bar       — cursor on line N+1
  6. \033[1B\r       — move DOWN 1 (not \n) to line N+2, col 0

Step 6 is the key fix: \033[1B moves to an already-existing line so the
terminal never scrolls, and the cursor returns to the same baseline after
every render so the next \033[2A always lands on the correct line N.
"""
import sys
import shutil

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"

FILL  = "█"
EMPTY = "░"


def _visible_len(s: str) -> int:
    """Length of s with ANSI escape sequences stripped."""
    import re
    return len(re.sub(r"\033\[[0-9;]*m", "", s))


class ProgressDisplay:
    def __init__(self, total: int, out=None):
        self.total   = max(total, 1)
        self.current = 0
        self._out    = out or sys.__stderr__
        self._tty    = hasattr(self._out, "isatty") and self._out.isatty()
        self._ready  = False

    # ------------------------------------------------------------------ public

    def update(self, n: int, msg: str = ""):
        self.current = n
        self._render(msg, is_warn=False)

    def info(self, msg: str):
        self._render(msg, is_warn=False)

    def warn(self, msg: str):
        self._render(msg, is_warn=True)

    def finish(self, summary: str = ""):
        self.current = self.total
        self._render(f"✓  {summary}" if summary else "✓  Done", is_warn=False)
        if self._tty:
            # Leave cursor below the footer, not sitting on top of it
            self._out.write("\n")
            self._out.flush()

    # --------------------------------------------------------------- internals

    def _width(self) -> int:
        return shutil.get_terminal_size((80, 24)).columns

    def _ensure_ready(self):
        if not self._ready:
            # Reserve two lines for the footer; cursor ends at N+2
            self._out.write("\n\n")
            self._out.flush()
            self._ready = True

    def _render(self, msg: str, is_warn: bool):
        if not self._tty:
            if msg:
                prefix = "[WARN]" if is_warn else "[INFO]"
                self._out.write(f"{prefix} {msg}\n")
                self._out.flush()
            return

        self._ensure_ready()
        width = self._width()
        o = self._out

        # ── Step 1-3: move to line N and write message ───────────────────
        o.write("\033[2A\r\033[2K")   # up 2 lines, col 0, clear line
        if msg:
            if is_warn:
                color, icon = YELLOW, "⚠  "
            elif msg.startswith("✓"):
                color, icon = GREEN,  ""
            else:
                color, icon = CYAN,   "●  "
            body = msg.lstrip("✓ ").strip() if msg.startswith("✓") else msg
            # Truncate so the line never wraps
            max_body = width - len(icon) - 1
            if len(body) > max_body:
                body = body[:max_body - 1] + "…"
            o.write(f"{BOLD}{color}{icon}{RESET}{color}{body}{RESET}")

        # ── Step 4-5: move to line N+1 and write bar ────────────────────
        o.write("\n\r\033[2K")        # down to N+1, col 0, clear line
        pct       = self.current / self.total
        bar_width = max(10, min(40, width - 24))
        filled    = int(bar_width * pct)
        empty     = bar_width - filled
        bar       = f"{GREEN}{FILL * filled}{DIM}{EMPTY * empty}{RESET}"
        pct_str   = f"{BOLD}{int(pct * 100):3d}%{RESET}"
        count_str = f"{self.current}/{self.total} entries"
        bar_line  = f"  {bar}  {pct_str}  {count_str}"
        # Hard-truncate to terminal width to prevent wrapping
        if _visible_len(bar_line) > width - 1:
            bar_line = bar_line[:width - 2]
        o.write(bar_line)

        # ── Step 6: return cursor to baseline N+2 without scrolling ─────
        o.write("\033[1B\r")          # down 1 existing line, col 0
        o.flush()


class ProgressStderr:
    """
    sys.stderr replacement that routes every completed line through a
    ProgressDisplay. Install after the TUI is done; restore before curses
    re-enters for sub-database prompts.
    """

    def __init__(self, display: ProgressDisplay):
        self._display = display
        self._buf     = ""

    def write(self, text: str):
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            if line.startswith("[WARN]"):
                self._display.warn(line[len("[WARN]"):].strip())
            else:
                self._display.info(line)

    def flush(self):
        if self._buf.strip():
            self._display.info(self._buf.strip())
            self._buf = ""

    def isatty(self):
        return False
