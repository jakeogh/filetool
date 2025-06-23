import pytest
from pathlib import Path
from filetool import append_bytes_to_file

def test_append_bytes_to_file_comment_marker_without_unique_bytes():
    with pytest.raises(ValueError, match=r"comment_marker requires unique_bytes=True"):
        append_bytes_to_file(
            bytes_payload=b"test\n",
            path=Path("/tmp/dummy"),
            unlink_first=False,
            unique_bytes=False,             # Invalid: comment_marker requires this to be True
            comment_marker=b"#",
            create_if_missing=True,
            make_parents=False,
        )
