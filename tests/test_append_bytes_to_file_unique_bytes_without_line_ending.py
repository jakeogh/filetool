import pytest
from pathlib import Path
from filetool import append_bytes_to_file

def test_append_bytes_to_file_unique_bytes_without_line_ending():
    with pytest.raises(ValueError, match="unique_bytes=True requires line_ending"):
        append_bytes_to_file(
            bytes_payload=b"test\n",
            path=Path("/tmp/dummy"),
            unlink_first=False,
            unique_bytes=True,          # Enabled uniqueness
            line_ending=None,           # Invalid: required if unique_bytes=True
            create_if_missing=True,
            make_parents=False,
        )
