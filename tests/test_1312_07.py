#!/usr/bin/env python3
"""
DEBUG: What is stripped value?
"""

import sys
from pathlib import Path
from filetool import uncomment_line_in_file


def trace_with_values(frame, event, arg):
    """Trace with variable inspection."""
    if event == 'line':
        filename = frame.f_code.co_filename
        lineno = frame.f_lineno

        if 'filetool.py' in filename and 1310 <= lineno <= 1315:
            print(f"Line {lineno}")

            # Try to get local variables
            if 'stripped' in frame.f_locals:
                stripped = frame.f_locals['stripped']
                print(f"  stripped = {stripped!r}")
            if 'line_ending' in frame.f_locals:
                line_ending = frame.f_locals['line_ending']
                print(f"  line_ending = {line_ending!r}")
            if 'compare_content' in frame.f_locals:
                compare_content = frame.f_locals['compare_content']
                print(f"  compare_content = {compare_content!r}")

    return trace_with_values


def test_debug():
    test_file = Path("/tmp/debug.txt")
    test_file.write_bytes(b"#   \n# target\n")

    try:
        sys.settrace(trace_with_values)

        result = uncomment_line_in_file(
            path=test_file,
            line="target",
            comment_marker="#",
            ignore_leading_whitespace=True,
            ignore_trailing_whitespace=True,
        )

        sys.settrace(None)
        print(f"\nResult: {result}")

    finally:
        test_file.unlink(missing_ok=True)


if __name__ == "__main__":
    test_debug()
