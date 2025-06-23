import pytest
from pathlib import Path
from filetool import append_bytes_to_file

def test_append_bytes_to_file_comment_marker_non_bytes_type():
    with pytest.raises(TypeError, match=r"comment_marker must be of type \(<class 'bytes'>, <class 'NoneType'>\), got str"):
        append_bytes_to_file(
            bytes_payload=b"test\n",
            path=Path("/tmp/dummy"),
            unlink_first=False,
            unique_bytes=True,
            comment_marker="#",               # Invalid type: str instead of bytes
            line_ending=b"\n",
            create_if_missing=True,
            make_parents=False,
        )
