import pytest
from pathlib import Path
from filetool import append_bytes_to_file

def test_append_bytes_to_file_incorrect_type_line_ending_without_unique_bytes():
    with pytest.raises(TypeError, match=r"line_ending must be of type \(<class 'bytes'>, <class 'NoneType'>\), got int"):
        append_bytes_to_file(
            bytes_payload=b"test\n",
            path=Path("/tmp/dummy"),
            unlink_first=False,
            unique_bytes=False,
            line_ending=123,
            create_if_missing=True,
            make_parents=False,
        )
