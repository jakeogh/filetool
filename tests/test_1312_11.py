#!/usr/bin/env python3
"""
Trace EXACTLY lines 1312-1317
"""

import sys
from pathlib import Path
from filetool import uncomment_line_in_file


def trace_1312(frame, event, arg):
    if event == 'line':
        filename = frame.f_code.co_filename
        lineno = frame.f_lineno

        if 'filetool.py' in filename and 1299 <= lineno <= 1320:
            line_ending = frame.f_locals.get('line_with_ending', b'?')
            if b'# ' in line_ending and len(line_ending) <= 10:
                print(f"Line {lineno}")
                if lineno == 1312:
                    print(f"  *** LINE 1312 EXECUTED! ***")

    return trace_1312


def test():
    test_file = Path("/tmp/t.txt")
    test_file.write_bytes(b"# \n# target\n")

    try:
        sys.settrace(trace_1312)
        result = uncomment_line_in_file(
            path=test_file,
            line="target",
            comment_marker="#",
            ignore_leading_whitespace=True,
            ignore_trailing_whitespace=True,
        )
        sys.settrace(None)

        print(f"\nResult: {result}")
        print("If you see '*** LINE 1312 EXECUTED! ***' above, we hit it!")

    finally:
        test_file.unlink(missing_ok=True)


if __name__ == "__main__":
    test()
