import pytest
from filetool import append_bytes_to_file

def test_append_bytes_to_file_non_pathlib_path():
    with pytest.raises(TypeError, match=r"path must be of type .*Path"):
        append_bytes_to_file(
            bytes_payload=b"test\n",
            path="/tmp/not_a_path_object",  # str instead of Path
            unlink_first=False,
            unique_bytes=False,
            create_if_missing=True,
            make_parents=False,
        )
