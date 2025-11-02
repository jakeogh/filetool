#!/usr/bin/env python3
"""
Debug: Why doesn't " " match "#   \n"?
"""

def test_debug():
    # Simulate the matching logic
    line = " "
    line_bytes = line.encode("utf-8")  # b' '
    line_ending = b"\n"
    comment_prefix = b"# "

    # File has: b"#   \n"
    file_line = b"#   \n"

    # After removing "# ": b"  \n"
    content_after_marker = file_line[len(comment_prefix):]
    print(f"content_after_marker: {content_after_marker!r}")

    # Build expected
    expected_content = line_bytes + line_ending
    print(f"expected_content: {expected_content!r}")

    # Apply leading whitespace handling
    compare_content = content_after_marker
    stripped = compare_content.lstrip()
    print(f"stripped: {stripped!r}")

    if stripped == line_ending or len(stripped) == 0:
        compare_content = line_ending
        print("✓ Line 1312: compare_content = line_ending")
    else:
        compare_content = stripped
        print("✗ Line 1314: compare_content = stripped")

    print(f"compare_content after leading: {compare_content!r}")

    # Apply trailing whitespace handling
    if compare_content.endswith(line_ending):
        content_part = compare_content[:-len(line_ending)]
        compare_content = content_part.rstrip() + line_ending

    print(f"Final compare_content: {compare_content!r}")
    print(f"Matches expected? {compare_content == expected_content}")

    if compare_content == expected_content:
        print("✓ MATCH! Line 1312 would execute and match!")
    else:
        print("✗ No match. Line 1312 executes but comparison fails.")


if __name__ == "__main__":
    test_debug()
