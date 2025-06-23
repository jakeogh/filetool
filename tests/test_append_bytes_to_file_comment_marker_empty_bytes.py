import pytest
from pathlib import Path
from filetool import append_bytes_to_file

def test_append_bytes_to_file_comment_marker_empty_bytes():
    with pytest.raises(ValueError, match="comment_marker must not be empty if set"):
        append_bytes_to_file(
            bytes_payload=b"test\n",
            path=Path("/tmp/dummy"),
            unlink_first=False,
            unique_bytes=True,
            comment_marker=b"",             # Invalid: empty bytes
            line_ending=b"\n",
            create_if_missing=True,
            make_parents=False,
        )
