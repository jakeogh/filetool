#!/usr/bin/env python3
"""
FINAL DEBUG - Check if line is found as commented
"""

from pathlib import Path
from filetool import uncomment_line_in_file


def test_is_line_found_as_commented():
    """
    The function raises ValueError if line is not found.
    So if we don't get an error, the line WAS found and processed.
    """
    test_file = Path("/tmp/final_debug.txt")

    # This should definitely be found as commented
    test_file.write_text("# mytarget\n")

    try:
        result = uncomment_line_in_file(
            path=test_file,
            line="mytarget",
            comment_marker="#",
            ignore_leading_whitespace=True,
            ignore_trailing_whitespace=True,
        )

        print(f"SUCCESS: Found and uncommented. Result={result}")

        if result == 0:
            print("WARNING: Result is 0, line might already be uncommented?")

        print(f"File now: {test_file.read_text()!r}")

    except ValueError as e:
        print(f"ERROR: {e}")
    finally:
        test_file.unlink(missing_ok=True)


if __name__ == "__main__":
    test_is_line_found_as_commented()
