import pytest
from pathlib import Path
from filetool import append_bytes_to_file


def test_append_bytes_to_file_invalid_type_unlink_first():
    with pytest.raises(TypeError, match=r"unlink_first must be of type <class 'bool'>"):
        append_bytes_to_file(
            bytes_payload=b"abc",
            path=Path("/tmp/dummy"),
            unique_bytes=True,
            line_ending=b"\n",
            unlink_first="yes",  # Invalid type
            create_if_missing=True,
            make_parents=False,
        )
