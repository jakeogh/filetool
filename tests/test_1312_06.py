#!/usr/bin/env python3
"""
PROVE LINE 1312 EXECUTES - Use sys.settrace
"""

import sys
from pathlib import Path
from filetool import uncomment_line_in_file


def trace_calls(frame, event, arg):
    """Trace function to see what lines execute."""
    if event == 'line':
        filename = frame.f_code.co_filename
        lineno = frame.f_lineno

        # Only trace filetool.py
        if 'filetool.py' in filename:
            if 1310 <= lineno <= 1315:
                print(f"TRACE: {filename}:{lineno}")

    return trace_calls


def test_with_trace():
    """Run with Python trace to see execution."""
    test_file = Path("/tmp/trace_test.txt")
    test_file.write_bytes(b"#   \n# target\n")

    try:
        # Enable tracing
        sys.settrace(trace_calls)

        result = uncomment_line_in_file(
            path=test_file,
            line="target",
            comment_marker="#",
            ignore_leading_whitespace=True,
            ignore_trailing_whitespace=True,
        )

        # Disable tracing
        sys.settrace(None)

        print(f"\nResult: {result}")
        print(f"If you see 'TRACE: ...filetool.py:1312' above, line 1312 WAS executed!")

    finally:
        test_file.unlink(missing_ok=True)


if __name__ == "__main__":
    test_with_trace()
