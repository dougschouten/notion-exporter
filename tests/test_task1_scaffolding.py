"""Task 1 tests: CLI argument parsing and database ID extraction."""
import os
import subprocess
import sys
import re

PYTHON = sys.executable
CLI = "cli.py"


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_DIR, "src")


def run_cli(*args):
    env = os.environ.copy()
    env["PYTHONPATH"] = SRC_DIR
    result = subprocess.run(
        [PYTHON, "-m", "notion_exporter.cli"] + list(args),
        capture_output=True, text=True, env=env,
    )
    return result


def test_help():
    r = run_cli("--help")
    assert r.returncode == 0, f"--help failed: {r.stderr}"
    for flag in ["url", "--token", "--start", "--end", "--output"]:
        assert flag in r.stdout, f"Missing '{flag}' in --help output"
    print("PASS: --help shows all arguments")


def test_bad_date_order():
    r = run_cli(
        "https://www.notion.so/ideon/15426c37bff781f9b6b5ead5af23a85f",
        "--token", "fake",
        "--start", "2024-12-01",
        "--end", "2024-01-01",
    )
    assert r.returncode != 0, "Should exit non-zero on bad date order"
    assert "after" in r.stderr.lower() or "error" in r.stderr.lower(), \
        f"Expected error message, got: {r.stderr}"
    print("PASS: reversed dates → clean error exit")


def test_database_id_extraction():
    import importlib.util, sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
    from notion_exporter.cli import extract_database_id

    url = "https://www.notion.so/ideon/15426c37bff781f9b6b5ead5af23a85f?v=15426c37bff781faba43000cdd4e0dd8"
    db_id = extract_database_id(url)
    print(f"  Extracted ID: {db_id}")
    assert re.fullmatch(r"[0-9a-f]{32}", db_id, re.IGNORECASE), \
        f"Expected 32-char hex, got: {db_id!r}"
    assert db_id == "15426c37bff781f9b6b5ead5af23a85f"
    print("PASS: database ID extraction correct")


if __name__ == "__main__":
    test_help()
    test_bad_date_order()
    test_database_id_extraction()
    print("\nAll Task 1 tests passed.")
