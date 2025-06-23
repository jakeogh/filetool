import pytest
from pathlib import Path
from filetool import append_bytes_to_file

def test_append_bytes_to_file_line_ending_without_unique_bytes():
    with pytest.raises(ValueError, match="line_ending requires unique_bytes=True"):
        append_bytes_to_file(
            bytes_payload=b"test\n",
            path=Path("/tmp/dummy"),
            unlink_first=False,
            unique_bytes=False,
            line_ending=b'\n',
            create_if_missing=True,
            make_parents=False,
        )
