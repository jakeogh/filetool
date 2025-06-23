import pytest
from pathlib import Path
from filetool import append_bytes_to_file

def test_append_bytes_to_file_comment_marker_type_none_with_unique_bytes():
    append_bytes_to_file(
        bytes_payload=b"abc",
        path=Path("/tmp/dummy"),
        unique_bytes=True,
        line_ending=b"\n",
        comment_marker=None,
        create_if_missing=True,
        make_parents=False,
        unlink_first=False,
    )