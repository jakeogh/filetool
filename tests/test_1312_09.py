#!/usr/bin/env python3
"""
FINAL TEST - Trace the whitespace-only commented line
"""

import sys
from pathlib import Path
from filetool import uncomment_line_in_file


def trace_line_1312(frame, event, arg):
    if event == 'line':
        filename = frame.f_code.co_filename
        lineno = frame.f_lineno

        if 'filetool.py' in filename and 1308 <= lineno <= 1316:
            locals_dict = frame.f_locals

            # Only print when we're in the transformer for the first line
            line_with_ending = locals_dict.get('line_with_ending')
            if line_with_ending and line_with_ending.startswith(b'# ') and len(line_with_ending) <= 3:
                print(f"Line {lineno}: Processing {line_with_ending!r}")

                if 'stripped' in locals_dict:
                    print(f"  stripped = {locals_dict['stripped']!r}")
                if 'compare_content' in locals_dict:
                    print(f"  compare_content = {locals_dict['compare_content']!r}")

    return trace_line_1312


def test():
    test_file = Path("/tmp/final_test.txt")
    test_file.write_bytes(b"# \n# target\n")

    try:
        sys.settrace(trace_line_1312)

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
    test()
