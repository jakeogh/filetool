# test_partial_match_conflict.py
import tempfile
from pathlib import Path
from filetool import append_bytes_to_file

def test_partial_byte_match_does_not_block_append():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "testfile"

        # Write full line
        append_bytes_to_file(
            bytes_payload=b"hello-world\n",
            path=path,
            unique_bytes=True,
            line_ending=b'\n',
            create_if_missing=True,
            make_parents=False,
            unlink_first=False,
        )

        # Try appending a substring
        append_bytes_to_file(
            bytes_payload=b"world\n",  # This is a substring of the previous line
            path=path,
            unique_bytes=True,
            line_ending=b'\n',
            create_if_missing=True,
            make_parents=False,
            unlink_first=False,
        )

        content = path.read_bytes()
        assert content == b"hello-world\nworld\n"

