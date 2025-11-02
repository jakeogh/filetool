#!/usr/bin/env python3
"""
DEBUG: What do the lines look like after splitlines_bytes?
"""

from pathlib import Path
from filetool.splitlines_bytes import splitlines_bytes


def test_splitlines_output():
    """See what splitlines_bytes produces."""
    test_file = Path("/tmp/debug_split.txt")
    test_file.write_bytes(b"# \n# target\n")

    try:
        with open(test_file, 'rb') as fh:
            lines = list(splitlines_bytes(
                fh,
                delim=b'\n',
                comment_marker=None,
                strip_leading_whitespace=False,
                strip_trailing_whitespace=False,
            ))

        print("Lines from splitlines_bytes:")
        for i, line in enumerate(lines):
            print(f"  Line {i}: {line!r}")

        # Now check what happens in uncomment
        print("\nProcessing in uncomment_line_in_file:")
        print("  First line starts with b'# ': ", lines[0].startswith(b'# '))
        print("  After removing b'# ': ", lines[0][2:] if lines[0].startswith(b'# ') else "N/A")

        # Check if it matches the pattern for line 1312
        if lines[0].startswith(b'# '):
            content_after = lines[0][2:]
            print(f"  content_after_marker: {content_after!r}")
            stripped = content_after.lstrip()
            print(f"  stripped: {stripped!r}")
            print(f"  len(stripped): {len(stripped)}")
            print(f"  Will hit line 1312? {stripped == b'\\n' or len(stripped) == 0}")

    finally:
        test_file.unlink(missing_ok=True)


if __name__ == "__main__":
    test_splitlines_output()
