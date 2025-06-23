import pytest
from pathlib import Path
from filetool import append_bytes_to_file

def test_append_bytes_to_file_invalid_type_ignore_leading_whitespace():
    with pytest.raises(TypeError, match=r"ignore_leading_whitespace must be of type <class 'bool'>"):
        append_bytes_to_file(
            bytes_payload=b"abc",
            path=Path("/tmp/dummy"),
            unique_bytes=True,
            line_ending=b"\n",
            ignore_leading_whitespace="true",  # Invalid
            create_if_missing=True,
            make_parents=False,
            unlink_first=False,
        )
