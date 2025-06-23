#!/usr/bin/env python3
import os
import tempfile
import pytest
from pathlib import Path

# Assuming filetool.py is in the same directory or importable
from filetool import append_bytes_to_file



def test_filetool_triggers_create_with_wronly_mode():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = Path(tmpdir) / "force_create_trigger.bin"
        assert not test_path.exists()  # force create=True path

        payload = b"unique line\n"

        # We force a condition that guarantees the file will be created
        bytes_written = append_bytes_to_file(
            bytes_payload=payload,
            path=test_path,
            unlink_first=False,
            unique_bytes=True,
            create_if_missing=True,
            make_parents=False,
            line_ending=b"\n",
            comment_marker=None,
            ignore_leading_whitespace=False,
            ignore_trailing_whitespace=False,
        )

        # Success means no crash, and file was created and written
        assert bytes_written == len(payload)
        assert test_path.read_bytes() == payload
