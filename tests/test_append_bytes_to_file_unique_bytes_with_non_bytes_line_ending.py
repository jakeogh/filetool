import pytest
from pathlib import Path
from filetool import append_bytes_to_file

def test_append_bytes_to_file_unique_bytes_with_non_bytes_line_ending():
    with pytest.raises(TypeError, match=r"line_ending must be of type \(<class 'bytes'>, <class 'NoneType'>\), got str"):
        append_bytes_to_file(
            bytes_payload=b"test\n",
            path=Path("/tmp/dummy"),
            unlink_first=False,
            unique_bytes=True,          # Enabled uniqueness
            line_ending='',             # Invalid: bytes required if unique_bytes=True
            create_if_missing=True,
            make_parents=False,
        )
