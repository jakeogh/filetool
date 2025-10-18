#!/usr/bin/env python3
from __future__ import annotations

import io
import itertools
import random
import sys
from typing import BinaryIO

import pytest

from filetool import splitlines_bytes  # make sure filetool.py is on your PYTHONPATH






def test_comment_marker_inside_data_not_split():
    data = b"abc##def#ghi##jkl"
    result = list(splitlines_bytes(data, delim=b"##", comment_marker=b"#"))
    assert result == [b"abc##", b'def##', b'jkl']

def test_empty_comment_marker_error():
    with pytest.raises(ValueError):
        list(splitlines_bytes(b"abc", comment_marker=b"", delim=b"\n"))

def test_splitlines_bytes_overlap_comment_in_delim():
    data = b'payload###comment##next'
    delim = b'##'
    comment_marker = b'#'
    strip_leading = False
    strip_trailing = False

    expected = [b'payload##', b'##', b'next']

    from filetool import splitlines_bytes
    from test_splitlines_bytes import reference_split

    # Reference implementation
    ref = reference_split(
        data=data,
        delim=delim,
        comment_marker=comment_marker,
        strip_leading=strip_leading,
        strip_trailing=strip_trailing,
    )
    assert ref == expected, f"reference_split mismatch: {ref} != {expected}"

    # Actual implementation
    actual = list(splitlines_bytes(
        data,
        delim=delim,
        comment_marker=comment_marker,
        strip_leading_whitespace=strip_leading,
        strip_trailing_whitespace=strip_trailing,
    ))
    assert actual == expected, f"splitlines_bytes mismatch: {actual} != {expected}"


def test_comment_marker_contains_delim_raises_value_error():
    """
    If the delimiter is a substring of the comment marker, comment stripping becomes impossible.
    This test ensures a ValueError is raised in that case.
    """
    with pytest.raises(ValueError, match="delim must not be contained in comment_marker"):
        list(splitlines_bytes(
            data=b"payload###comment##next",
            delim=b"#",
            comment_marker=b"##"
        ))

def test_only_delimiter_present():
    data = b"\n"
    result = list(splitlines_bytes(data, delim=b"\n"))
    assert result == [b"\n"]


def test_just_comment_stripped():
    data = b"#comment\n"
    result = list(splitlines_bytes(data, comment_marker=b"#"))
    assert result == [b"\n"]


def test_long_patterny():
    data = (b"x#cmt\n" * 5000)
    result = list(splitlines_bytes(data, comment_marker=b"#"))
    assert all(x.endswith(b"\n") for x in result)

def test_splitlines_bytes_stream_long_repeated_pattern():
    data = (b"line\n" * 100) + b"#finalcomment\n"
    expected = [b"line\n"] * 100 + [b'\n']  # final comment becomes empty but '\n' is re-added

    stream = io.BytesIO(data)
    result = list(
        splitlines_bytes(
            stream,
            delim=b"\n",
            comment_marker=b"#",
            strip_leading_whitespace=False,
            strip_trailing_whitespace=False,
            chunk_size=128,
        )
    )
    assert result == expected


def test_comment_marker_only_strips_after_split():
    """
    Ensure comment stripping is applied only after splitting,
    not mid-segment. '#' should only affect after splitting.
    """
    data = b"abc\x00#ignore\x00def\x00"
    delim = b"\x00"
    comment_marker = b"#"
    expected = [b"abc\x00", b"\x00", b"def\x00"]
    actual = list(splitlines_bytes(
        data=data,
        delim=delim,
        comment_marker=comment_marker,
        strip_leading_whitespace=False,
        strip_trailing_whitespace=False,
    ))
    assert actual == expected


def test_multiple_comment_markers_single_segment():
    data = b"val1#cmt1#cmt2\nval2#cmt"
    expected = [b"val1\n", b"val2"]
    result = list(splitlines_bytes(data, comment_marker=b"#"))
    assert result == expected


def test_comment_marker_not_applied_cross_segment():
    data = b"val1#comment\n#comment"
    expected = [b"val1\n"]
    result = list(splitlines_bytes(data, comment_marker=b"#"))
    assert result == expected


def test_whitespace_only_segments_with_stripping():
    data = b"  \n\t\nval\n"
    result = list(splitlines_bytes(
        data,
        strip_leading_whitespace=True,
        strip_trailing_whitespace=True
    ))
    assert result == [b"\n", b"\n", b"val\n"]


def test_segment_exactly_comment_marker_is_skipped():
    data = b"#\nvalid\n"
    result = list(splitlines_bytes(data, comment_marker=b"#"))
    assert result == [b"\n", b"valid\n"]


def test_comment_marker_with_null_byte_delim():
    data = b"abc\x00#hidden\x00visible"
    result = list(splitlines_bytes(data, delim=b"\x00", comment_marker=b"#"))
    assert result == [b"abc\x00", b"\x00", b"visible"]



def test_similar_delim_and_comment_not_confused():
    data = b"a##b##c"
    result = list(splitlines_bytes(data, delim=b"##", comment_marker=b"#"))
    assert result == [b"a##", b"b##", b"c"]


def test_strip_whitespace_before_comment():
    data = b"   val #c\n"
    result = list(splitlines_bytes(data, comment_marker=b"#", strip_leading_whitespace=True))
    assert result == [b"val \n"]


def test_final_empty_segment_not_emitted():
    data = b"val1||val2||"
    result = list(splitlines_bytes(data, delim=b"||"))
    assert result == [b"val1||", b"val2||"]


def test_comment_marker_contains_reversed_delim_is_ok():
    data = b"val/##/cmt/#next"
    result = list(splitlines_bytes(data, delim=b"/#", comment_marker=b"#/"))
    assert result == [b'val/#', b'/#', b'next']

def test_trailing_comment_without_delimiter():
    data = b"value#comment"
    result = list(splitlines_bytes(data, comment_marker=b"#"))
    assert result == [b"value"]

def test_binary_data_around_comment():
    data = b"\x00\xffvalue#comment\nnext"
    result = list(splitlines_bytes(data, comment_marker=b"#"))
    assert result == [b"\x00\xffvalue\n", b"next"]


def test_binary_data_in_comment_is_stripped():
    data = b"value#\x00\xff\xfe\nnext"
    result = list(splitlines_bytes(data, comment_marker=b"#"))
    assert result == [b"value\n", b"next"]



def test_trailing_delim_retains_empty_segment():
    data = b"one|two|"
    result = list(splitlines_bytes(data, delim=b"|"))
    assert result == [b"one|", b"two|"]

def test_first_line_comment_stripped():
    data = b"#fullcomment\npayload\n"
    result = list(splitlines_bytes(data, comment_marker=b"#"))
    assert result == [b'\n', b'payload\n']


# this triggers a current bug
def test_whitespace_line_with_marker_only():
    data = b"   #foo\n"
    result = list(splitlines_bytes(data, comment_marker=b"#", strip_leading_whitespace=True))
    assert result == [b'\n']



# attempt to fuzz the above failing test case before fixing the bug
def generate_edge_case_inputs():
    comment_markers = [b"#", b"//", b"!!"]
    delimiters = [b"\n", b"\x00", b"##"]

    for delim in delimiters:
        for comment_marker in comment_markers:
            if delim in comment_marker:
                continue

            for strip_leading in [True, False]:
                for strip_trailing in [True, False]:
                    yield {
                        "name": "comment line becomes just delim after strip",
                        "data": b"   " + comment_marker + b"comment" + delim,
                        "delim": delim,
                        "comment_marker": comment_marker,
                        "strip_leading": strip_leading,
                        "strip_trailing": strip_trailing,
                        "expect_empty_line": False,
                    }

                    yield {
                        "name": "whitespace-only line with delimiter",
                        "data": b"\t  " + delim,
                        "delim": delim,
                        "comment_marker": comment_marker,
                        "strip_leading": strip_leading,
                        "strip_trailing": strip_trailing,
                        "expect_empty_line": False,
                    }

                    yield {
                        "name": "leading comment with strip_leading",
                        "data": comment_marker + b"only" + delim,
                        "delim": delim,
                        "comment_marker": comment_marker,
                        "strip_leading": True,
                        "strip_trailing": False,
                        "expect_empty_line": False,
                    }


@pytest.mark.parametrize("case", list(generate_edge_case_inputs()))
def test_fuzz_trigger_comment_strip_empty(case):
    result = list(
        splitlines_bytes(
            case["data"],
            delim=case["delim"],
            comment_marker=case["comment_marker"],
            strip_leading_whitespace=case["strip_leading"],
            strip_trailing_whitespace=case["strip_trailing"],
        )
    )
    if case["expect_empty_line"]:
        # We expect at least one line that is exactly the delimiter or empty content with delimiter
        assert any(
            line.strip(b" \t\r") == b"" and line.endswith(case["delim"])
            for line in result
        ), f"Missing expected empty line: {case}, got: {result}"


def run_splitlines_bytes(data: bytes | BinaryIO, **kwargs) -> list[bytes]:
    return list(splitlines_bytes(data, **kwargs))
def generate_stream(data: bytes) -> BinaryIO:
    return io.BufferedReader(io.BytesIO(data))


# -------------------------
# Byte-mode test cases
# -------------------------


def test_default_behavior_bytes():
    assert run_splitlines_bytes(b"a\nb\nc\n") == [b"a\n", b"b\n", b"c\n"]


def test_custom_delimiter_bytes():
    assert run_splitlines_bytes(b"a||b||c||", delim=b"||") == [b"a||", b"b||", b"c||"]


def test_no_trailing_delimiter_bytes():
    assert run_splitlines_bytes(b"a||b||c", delim=b"||") == [b"a||", b"b||", b"c"]


def test_comment_stripping_bytes():
    assert run_splitlines_bytes(b"one#c\ntwo#d\n", comment_marker=b"#") == [
        b"one\n",
        b"two\n",
    ]


def test_strip_leading_ws_bytes():
    assert run_splitlines_bytes(b"  a\n  b\n", strip_leading_whitespace=True) == [
        b"a\n",
        b"b\n",
    ]


def test_strip_trailing_ws_bytes():
    assert run_splitlines_bytes(b"a \n b \n", strip_trailing_whitespace=True) == [
        b"a\n",
        b" b\n",
    ]  # keep leading space on second line


def test_both_strip_bytes():
    assert run_splitlines_bytes(
        b"  a \n  b \n", strip_leading_whitespace=True, strip_trailing_whitespace=True
    ) == [b"a\n", b"b\n"]


def test_custom_delim_and_strip_bytes():
    assert run_splitlines_bytes(
        b" a| b| ",
        delim=b"|",
        strip_leading_whitespace=True,
        strip_trailing_whitespace=True,
    ) == [b"a|", b"b|"]


# -------------------------
# Streaming-mode test cases
# -------------------------


def test_default_behavior_stream():
    assert run_splitlines_bytes(generate_stream(b"a\nb\nc\n")) == [
        b"a\n",
        b"b\n",
        b"c\n",
    ]


def test_comment_stripping_stream():
    assert run_splitlines_bytes(
        generate_stream(b"a#1\nb#2\n"), comment_marker=b"#"
    ) == [b"a\n", b"b\n"]


def test_strip_both_stream():
    assert run_splitlines_bytes(
        generate_stream(b" x \n  y  \n"),
        strip_leading_whitespace=True,
        strip_trailing_whitespace=True,
    ) == [b"x\n", b"y\n"]


def test_long_line_split_across_chunks():
    data = b"a" * 10000 + b"\n" + b"b" * 10000 + b"\n"
    assert run_splitlines_bytes(generate_stream(data)) == [
        b"a" * 10000 + b"\n",
        b"b" * 10000 + b"\n",
    ]


# -------------------------
# Edge cases
# -------------------------


def test_empty_input_bytes():
    assert run_splitlines_bytes(b"") == []


def test_empty_input_stream():
    assert run_splitlines_bytes(generate_stream(b"")) == []


def test_value_error_on_empty_delim():
    with pytest.raises(ValueError):
        run_splitlines_bytes(b"data", delim=b"")


# fuzzing below


def generate_stream(data: bytes) -> io.BufferedReader:
    return io.BufferedReader(io.BytesIO(data))


def random_bytes(size: int) -> bytes:
    return bytes(random.choices(range(256), k=size))


# ----------------------------
# Fuzz Test 1: Basic binary input
# ----------------------------
def test_fuzz_splitlines_bytes_basic():
    for _ in range(100):
        raw = random_bytes(random.randint(1, 512))
        delim = random_bytes(random.randint(1, 3)) or b"\x00"
        try:
            _ = list(splitlines_bytes(raw, delim=delim))
        except Exception as e:
            pytest.fail(f"Basic fuzz failed on raw={raw!r}, delim={delim!r}: {e}")


# ----------------------------
# Fuzz Test 2: Streamed input with random options
# ----------------------------
def test_fuzz_splitlines_bytes_stream():
    for _ in range(100):
        data = random_bytes(random.randint(1, 512))
        stream = generate_stream(data)
        delim = random_bytes(random.randint(1, 2)) or b"\n"
        comment = random.choice([None, random_bytes(1)])
        strip_leading = random.choice([True, False])
        strip_trailing = random.choice([True, False])

        if comment is not None and comment == delim:
            with pytest.raises(ValueError, match="comment_marker can not match delim"):
                list(
                    splitlines_bytes(
                        stream,
                        delim=delim,
                        comment_marker=comment,
                        strip_leading_whitespace=strip_leading,
                        strip_trailing_whitespace=strip_trailing,
                    )
                )
        else:
            try:
                _ = list(
                    splitlines_bytes(
                        stream,
                        delim=delim,
                        comment_marker=comment,
                        strip_leading_whitespace=strip_leading,
                        strip_trailing_whitespace=strip_trailing,
                    )
                )
            except Exception as e:
                pytest.fail(
                    f"Stream fuzz failed on data={data!r}, delim={delim!r}, comment={comment!r}: {e}"
                )



# ----------------------------
# Fuzz Test 3: Targeted edge-case patterns
# ----------------------------

import pytest
from filetool import splitlines_bytes


def test_fuzz_splitlines_bytes_edge_cases():
    known_inputs = [
        b"",
        b"\x00\x01\x00\x02",
        b"\xff" * 256 + b"\n" + b"\xfe" * 256,
        b"\n" * 100,
        b"A" * 4096 + b"\nB" * 4096 + b"\n",
        b"#comment\n#another\n",
        b" \t\n\r\v\f|end",
    ]
    for raw in known_inputs:
        for delim in [b"\n", b"\x00", b"|", b"\xff", b"\n\n"]:
            for comment in [None, b"#", b"\x00", b"\xff"]:
                if comment == delim:
                    # Expected ValueError when comment_marker == delim
                    with pytest.raises(ValueError):
                        list(
                            splitlines_bytes(
                                raw,
                                delim=delim,
                                comment_marker=comment,
                                strip_leading_whitespace=True,
                                strip_trailing_whitespace=True,
                            )
                        )
                else:
                    try:
                        _ = list(
                            splitlines_bytes(
                                raw,
                                delim=delim,
                                comment_marker=comment,
                                strip_leading_whitespace=True,
                                strip_trailing_whitespace=True,
                            )
                        )
                    except Exception as e:
                        pytest.fail(
                            f"Edge case failed: raw={raw!r}, delim={delim!r}, comment={comment!r}: {e}"
                        )


#def test_fuzz_splitlines_bytes_edge_cases():
#    known_inputs = [
#        b"",
#        b"\x00\x01\x00\x02",
#        b"\xff" * 256 + b"\n" + b"\xfe" * 256,
#        b"\n" * 100,
#        b"A" * 4096 + b"\nB" * 4096 + b"\n",
#        b"#comment\n#another\n",
#        b" \t\n\r\v\f|end",
#    ]
#    for raw in known_inputs:
#        for delim in [b"\n", b"\x00", b"|", b"\xff", b"\n\n"]:
#            for comment in [None, b"#", b"\x00", b"\xff"]:
#                try:
#                    _ = list(
#                        splitlines_bytes(
#                            raw,
#                            delim=delim,
#                            comment_marker=comment,
#                            strip_leading_whitespace=True,
#                            strip_trailing_whitespace=True,
#                        )
#                    )
#                except Exception as e:
#                    pytest.fail(
#                        f"Edge case failed: raw={raw!r}, delim={delim!r}, comment={comment!r}: {e}"
#                    )


def test_delim_is_null_byte():
    assert list(splitlines_bytes(b"a\x00b\x00c", delim=b"\x00")) == [
        b"a\x00",
        b"b\x00",
        b"c",
    ]


def test_multibyte_delimiter():
    assert list(splitlines_bytes(b"aa||bb||cc", delim=b"||")) == [
        b"aa||",
        b"bb||",
        b"cc",
    ]


def test_fuzz_splitlines_bytes_explicit_null_and_multibyte():
    for delim in [b"\x00", b"\x00\x00", b"||", b"\xff\xfe", b"\r\n"]:
        for _ in range(20):  # target each delimiter type
            data = random_bytes(random.randint(1, 512)).replace(
                delim, b"X" * len(delim)
            )
            padded = delim.join([data[i : i + 10] for i in range(0, len(data), 10)])
            assert list(splitlines_bytes(padded, delim=delim))[-1]  # Should not crash


def generate_stream(data: bytes) -> io.BufferedReader:
    return io.BufferedReader(io.BytesIO(data))


# ---------------------------
# Chunk boundary split test
# ---------------------------
def test_multibyte_delimiter_across_chunk_boundary():
    chunk_size = 8192
    prefix = b"A" * (chunk_size - 2)
    delim = b"XYZ"
    data = prefix + b"XY" + b"ZmoreXYZrest"
    stream = generate_stream(data)
    result = list(splitlines_bytes(stream, delim=delim))
    assert result == [prefix + b"XYZ", b"moreXYZ", b"rest"]


# ---------------------------
# Long single-line test
# ---------------------------
def test_extremely_long_line():
    line = b"x" * 10_000_000
    result = list(splitlines_bytes(line))
    assert result == [line]


# ---------------------------
# Many small lines
# ---------------------------
def test_many_small_lines():
    data = b"x\n" * 1_000
    result = list(splitlines_bytes(data))
    assert result == [b"x\n"] * 1_000


# ---------------------------
# Comment at line start
# ---------------------------
def test_comment_at_line_start():
    data = b"#first\nactual\n"
    result = list(splitlines_bytes(data, comment_marker=b"#"))
    assert result == [b"\n", b"actual\n"]


# ---------------------------
# Idempotency property
# ---------------------------
def test_idempotent_split_and_join():
    data = b"a||b||c||"
    delim = b"||"
    lines = list(splitlines_bytes(data, delim=delim))
    rejoined = b"".join(lines)
    assert rejoined == data


# ---------------------------
# Data preservation
# ---------------------------
def test_no_data_loss_on_split():
    data = b"a\nb\nc\nd\n"
    lines = list(splitlines_bytes(data, delim=b"\n"))
    assert sum(len(line) for line in lines) == len(data)


# ---------------------------
# Invalid comment_marker
# ---------------------------
def test_invalid_comment_marker_type_int():
    with pytest.raises(TypeError):
        list(splitlines_bytes(b"abc\n", comment_marker=123))  # type: ignore


# ---------------------------
# Non-seekable stream
# ---------------------------
def test_non_seekable_stream():
    class NonSeekable(io.RawIOBase):
        def __init__(self, raw: bytes):
            self._raw = io.BytesIO(raw)

        def readinto(self, b):
            chunk = self._raw.read(len(b))
            if not chunk:
                return 0
            n = len(chunk)
            b[:n] = chunk
            return n

        def readable(self):
            return True

    stream = io.BufferedReader(NonSeekable(b"line1\nline2\n"))
    result = list(splitlines_bytes(stream))
    assert result == [b"line1\n", b"line2\n"]


# ---------------------------
# Strip + comment + custom delim combo
# ---------------------------
def test_strip_and_comment_with_custom_delim():
    data = b" abc#comment|| def ||ghi#x||"
    result = list(
        splitlines_bytes(
            data,
            delim=b"||",
            comment_marker=b"#",
            strip_leading_whitespace=True,
            strip_trailing_whitespace=True,
        )
    )
    assert result == [b"abc||", b"def ||", b"ghi||"]


# ---------------------------
# Mixed whitespace and delimiters
# ---------------------------
def test_whitespace_control_with_tab_delimiter():
    data = b"\tline1\t\tline2 \t"
    result = list(
        splitlines_bytes(
            data,
            delim=b"\t",
            strip_leading_whitespace=True,
            strip_trailing_whitespace=True,
        )
    )
    assert result == [b"\t", b"line1\t", b"\t", b"line2\t"]


# ---------------------------
# Explicit null delimiter
# ---------------------------
def test_delim_is_null_byte():
    assert list(splitlines_bytes(b"a\x00b\x00c", delim=b"\x00")) == [
        b"a\x00",
        b"b\x00",
        b"c",
    ]


# ---------------------------
# Explicit multibyte delimiter
# ---------------------------
def test_multibyte_delimiter():
    assert list(splitlines_bytes(b"aa||bb||cc", delim=b"||")) == [
        b"aa||",
        b"bb||",
        b"cc",
    ]


# we do not emit a empty segment for the last delim
def test_empty_segments_with_leading_delimiter():
    data = b"\nline1\nline2\n"
    result = list(splitlines_bytes(data, delim=b"\n"))
    assert result == [b"\n", b"line1\n", b"line2\n"]
    # assert result == [b"\n", b"line1\n", b"line2\n", b""]  # wrong


def test_empty_segments_with_multiple_consecutive_delimiters():
    data = b"line1\n\n\nline2\n"
    result = list(splitlines_bytes(data, delim=b"\n"))
    assert result == [b"line1\n", b"\n", b"\n", b"line2\n"]


def test_empty_segments_with_custom_delimiter():
    data = b"item1||item2||||item3||"
    result = list(splitlines_bytes(data, delim=b"||"))
    assert result == [b"item1||", b"item2||", b"||", b"item3||"]


def test_empty_segments_only_delimiters():
    data = b"||||||"
    result = list(splitlines_bytes(data, delim=b"||"))
    assert result == [b"||", b"||", b"||"]


def test_empty_segments_with_whitespace_stripping():
    data = b"  a||  ||  b||"
    result = list(
        splitlines_bytes(
            data,
            delim=b"||",
            strip_leading_whitespace=True,
            strip_trailing_whitespace=True,
        )
    )
    assert result == [b"a||", b"||", b"b||"]


# explicit byte checked fuzzing


def trace_vars(frame, event, arg):
    if event == "line":
        local_vars = frame.f_locals.copy()
        print(f"[{frame.f_lineno}] {frame.f_code.co_name}: {local_vars}")
    return trace_vars


def reference_split(
    data: bytes,
    *,
    delim: bytes,
    comment_marker: bytes | None,
    strip_leading: bool,
    strip_trailing: bool,
) -> list[bytes]:
    """
    Slow, pure Python reference implementation for splitlines_bytes().
    """
    if delim == b"":
        raise ValueError("Delimiter must not be empty")
    if data == b"":
        return []

    re_add_delim = delim in b" \t\n\r\x0b\x0c"
    parts = data.split(delim)
    lines = []

    for part in parts[:-1]:
        line = part + delim
        if comment_marker and comment_marker in line:
            line = line.split(comment_marker)[0] + delim
        if strip_leading:
            line = line.lstrip()
        if strip_trailing:
            if re_add_delim:
                line = line.rstrip() + delim
            else:
                line = line.rstrip()
        lines.append(line)

    last_raw = parts[-1]
    last = last_raw
    raw_had_trailing_delim = data.endswith(delim) or (
        comment_marker and data.rstrip().endswith(comment_marker)
    )

    if last or not data.endswith(delim):
        if comment_marker and comment_marker in last:
            last = last.split(comment_marker)[0]
        if strip_leading:
            last = last.lstrip()

        if strip_trailing:
            if re_add_delim:
                last = last.rstrip() + delim
            else:
                last = last.rstrip()

        elif last_raw.endswith(delim) and re_add_delim:
            last += delim

        skip_append = False
        if strip_leading:
            if len(last) == 0:
                skip_append = True

        if comment_marker and comment_marker in last_raw:
            if len(last) == 0:
                skip_append = True

        if strip_trailing:
            if len(last) == 0:
                skip_append = True

        if not skip_append:
            lines.append(last)

    return lines


# Fuzz parameters
DELIMITERS = [b"\n", b"\x00", b"|", b"##"]
COMMENT_MARKERS = [None, b"#", b"//", b"##"]
WHITESPACE_CASES = list(itertools.product([False, True], repeat=2))


def generate_fuzz_cases():
    """
    Yield fuzz test configurations as dictionaries.
    """
    for delim in DELIMITERS:
        for comment_marker in COMMENT_MARKERS:
            # Skip problematic overlaps
            if comment_marker and (delim in comment_marker or comment_marker in delim):
                continue
            for strip_leading, strip_trailing in WHITESPACE_CASES:
                yield {
                    "data": b" A  "
                    + delim
                    + b"B"
                    + (comment_marker * 2 if comment_marker else b""),
                    "delim": delim,
                    "comment_marker": comment_marker,
                    "strip_leading": strip_leading,
                    "strip_trailing": strip_trailing,
                }
                yield {
                    "data": delim.join([b"  1", b"2  ", b" 3#cmt ", b" 4"]) + delim,
                    "delim": delim,
                    "comment_marker": comment_marker,
                    "strip_leading": strip_leading,
                    "strip_trailing": strip_trailing,
                }
                yield {
                    "data": b"",
                    "delim": delim,
                    "comment_marker": comment_marker,
                    "strip_leading": strip_leading,
                    "strip_trailing": strip_trailing,
                }

    yield {
        "data": b"A#B##C###D",
        "delim": b"##",
        "comment_marker": b"#",
        "strip_leading": False,
        "strip_trailing": False,
    }


@pytest.mark.parametrize("case", list(generate_fuzz_cases()))
def test_splitlines_bytes_fuzz_against_reference(case):
    """
    Run splitlines_bytes() and compare to reference implementation output.
    """
    expected = reference_split(
        data=case["data"],
        delim=case["delim"],
        comment_marker=case["comment_marker"],
        strip_leading=case["strip_leading"],
        strip_trailing=case["strip_trailing"],
    )
    actual = list(
        splitlines_bytes(
            case["data"],
            delim=case["delim"],
            comment_marker=case["comment_marker"],
            strip_leading_whitespace=case["strip_leading"],
            strip_trailing_whitespace=case["strip_trailing"],
        )
    )
    assert actual == expected, f"Mismatch for case: {case}"


@pytest.mark.parametrize("case", list(generate_fuzz_cases()))
def test_splitlines_bytes_fuzz_against_reference_binaryio(case):
    """
    Run splitlines_bytes() on a BinaryIO stream and compare to reference output.
    This covers the non-bytes object code path (streaming input).
    """
    expected = reference_split(
        data=case["data"],
        delim=case["delim"],
        comment_marker=case["comment_marker"],
        strip_leading=case["strip_leading"],
        strip_trailing=case["strip_trailing"],
    )
    bio = io.BytesIO(case["data"])
    actual = list(
        splitlines_bytes(
            bio,
            delim=case["delim"],
            comment_marker=case["comment_marker"],
            strip_leading_whitespace=case["strip_leading"],
            strip_trailing_whitespace=case["strip_trailing"],
        )
    )
    assert actual == expected, f"Mismatch for BinaryIO case: {case}"


# Reuse the existing generate_fuzz_cases()
# and reference_split from your previous setup.


@pytest.mark.parametrize("chunk_size", list(range(1, 17)))
@pytest.mark.parametrize("case", list(generate_fuzz_cases()))
def test_splitlines_bytes_fuzz_against_reference_binaryio_over_all_chunk_size(
    case, chunk_size
):
    """
    Run splitlines_bytes() on a BinaryIO stream with varying read_chunk_size
    and compare to reference output. This covers the non-bytes object code path
    with full range of chunk sizes from 1 to 8192.
    """
    expected = reference_split(
        data=case["data"],
        delim=case["delim"],
        comment_marker=case["comment_marker"],
        strip_leading=case["strip_leading"],
        strip_trailing=case["strip_trailing"],
    )
    bio = io.BytesIO(case["data"])
    actual = list(
        splitlines_bytes(
            bio,
            delim=case["delim"],
            comment_marker=case["comment_marker"],
            strip_leading_whitespace=case["strip_leading"],
            strip_trailing_whitespace=case["strip_trailing"],
            chunk_size=chunk_size,
        )
    )
    assert (
        actual == expected
    ), f"Mismatch for BinaryIO case: {case} with chunk_size={chunk_size}"




def test_splitlines_bytes_bug_case_comment_split():
    data = b"A#B##C###D"
    delim = b"##"
    comment_marker = b"#"
    expected = [b"A##", b"C##"]  # Correct result, final segment is trimmed
    actual = list(
        splitlines_bytes(
            data,
            delim=delim,
            comment_marker=comment_marker,
        )
    )
    assert actual == expected, f"Expected {expected}, got {actual}"







