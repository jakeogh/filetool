import pytest
from pathlib import Path
from filetool import append_bytes_to_file

def test_append_bytes_to_file_comment_marker_bytes_no_line_ending():
    with pytest.raises(ValueError, match="unique_bytes=True requires line_ending"):
        append_bytes_to_file(
            bytes_payload=b"abc",
            path=Path("/tmp/dummy"),
            unique_bytes=True,
            comment_marker=b"#",  # valid
            line_ending=None,     # missing but required
            create_if_missing=True,
            make_parents=False,
            unlink_first=False,
        )
