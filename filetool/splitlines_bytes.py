#!/usr/bin/env python3

from collections.abc import Iterator
from typing import BinaryIO

def splitlines_bytes(
    data: bytes | BinaryIO,
    *,
    delim: bytes = b"\n",
    comment_marker: None | bytes = None,
    strip_leading_whitespace: bool = False,
    strip_trailing_whitespace: bool = False,
    chunk_size: int = 8192,
) -> Iterator[bytes]:
    """
    Split raw bytes by a delimiter, optionally stripping whitespace or comments.

    Parameters:
        data (bytes | BinaryIO): Raw byte buffer or readable binary file-like object.
        delim (bytes): Delimiter to split on (default: b'\\n').
        comment_marker (bytes | None): If set, strip trailing content starting at this marker.
        strip_leading_whitespace (bool): Whether to strip leading whitespace from each line.
        strip_trailing_whitespace (bool): Whether to strip trailing whitespace from each line.
        chunk_size (int): Number of bytes to read from a BinaryIO object at a time.

    Yields:
        bytes: Processed line segments. Delimiters are always included in output except
               for the final line if it doesn't end with one.

    Note:
        - Unlike `bytes.splitlines()`, this supports custom delimiters, comment stripping,
          and whitespace control.
        - If `data` is a file-like object (e.g. `BinaryIO`), it will be read in chunks
          with minimal memory usage.
        - When `delim` is a whitespace character (space, tab, newline, etc.) and
          whitespace stripping is enabled, empty/comment-only lines will still yield
          the delimiter itself (e.g., b'\\n') to preserve line structure.
        - `strip_trailing_whitespace` only removes whitespace characters; if `delim` is
          not whitespace, spaces before the delimiter are preserved.
        - `comment_marker` can appear within `delim`, but `delim` cannot appear within
          `comment_marker` (raises ValueError).
    """

    # comment_marker can be in delim:
    # list(splitlines_bytes(data=b'payload###comment##next', delim=b'##', comment_marker=b'#'))
    # -> [b'payload##', b'##', b'next']

    # but delim in comment marker is disallowed because it silently disables comment stripping:
    # list(splitlines_bytes(data=b'payload###comment##next', delim=b'#', comment_marker=b'##'))
    # [b'payload#', b'#', b'#', b'comment#', b'#', b'next']

    if delim is None or len(delim) == 0:
        raise ValueError("delim must not be empty")

    if comment_marker is not None:
        if len(comment_marker) == 0:
            raise ValueError("comment_marker must not be empty")
        if not isinstance(comment_marker, bytes):
            raise TypeError("comment_marker must be bytes or None")
        if comment_marker == delim:
            # if this was allowed, it would silently disable comment stripping
            raise ValueError("comment_marker can not match delim")
        if comment_marker is not None and delim in comment_marker:
            # if this was allowed, it would silently disable comment stripping
            raise ValueError("delim must not be contained in comment_marker")

    strip_bytes = b" \t\n\r\x0b\x0c"  # changing this would be a bug because it's what l/rstrip use
    re_add_delim = delim in strip_bytes
    delim_len = len(delim)
    buffer = b""

    def process_line(line: bytes) -> None | bytes:
        _line = line
        if comment_marker and comment_marker in line:
            _line = line.split(comment_marker)[0]
            if line.endswith(delim):
                _line = _line + delim

        if strip_leading_whitespace:
            if line.endswith(delim):
                _line = _line.lstrip()
                if len(_line) == 0:
                    _line += delim
            else:
                _line = _line.lstrip()
        if strip_trailing_whitespace:
            if re_add_delim:
                _line = _line.rstrip() + delim
            else:
                _line = _line.rstrip()
            if _line == b"":
                return None
        if strip_leading_whitespace:
            if _line == b"":
                return None
        if comment_marker and comment_marker in line:
            if _line == b"":
                return None
        # assert len(_line) > 0
        return _line

    if isinstance(data, bytes):
        start = 0
        while True:
            idx = data.find(delim, start)
            if idx == -1:
                if start < len(data):
                    line = data[start:]
                    _pl = process_line(line)
                    if _pl is not None:
                        yield _pl
                break
            end = idx + delim_len
            line = data[start:end]
            _pl = process_line(line)
            if _pl is not None:
                yield _pl
            start = end
    else:
        while True:
            chunk = data.read(chunk_size)
            if not chunk:
                break
            buffer += chunk
            while True:
                idx = buffer.find(delim)
                if idx == -1:
                    break
                end = idx + delim_len
                line = buffer[:end]
                _pl = process_line(line)
                if _pl is not None:
                    yield _pl
                buffer = buffer[end:]

        if buffer:
            _pl = process_line(buffer)
            if _pl is not None:
                yield _pl
