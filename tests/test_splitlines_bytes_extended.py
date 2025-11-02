import io

import pytest

from filetool.splitlines_bytes import splitlines_bytes


class TestBasicSplitting:
    """Test basic delimiter splitting without extras"""

    @pytest.mark.parametrize(
        "data,delim,expected",
        [
            (b"a\nb\nc", b"\n", [b"a\n", b"b\n", b"c"]),
            (b"a\nb\nc\n", b"\n", [b"a\n", b"b\n", b"c\n"]),
            (b"one##two##three", b"##", [b"one##", b"two##", b"three"]),
            (b"one##two##three##", b"##", [b"one##", b"two##", b"three##"]),
            (b"", b"\n", []),
            (b"single", b"\n", [b"single"]),
            (b"\n", b"\n", [b"\n"]),
            (b"\n\n", b"\n", [b"\n", b"\n"]),
            (b"a|b|c", b"|", [b"a|", b"b|", b"c"]),
        ],
    )
    def test_basic_split_bytes(
        self,
        data,
        delim,
        expected,
    ):
        result = list(splitlines_bytes(data, delim=delim))
        assert result == expected

    @pytest.mark.parametrize(
        "data,delim,expected",
        [
            (b"a\nb\nc", b"\n", [b"a\n", b"b\n", b"c"]),
            (b"one##two##three", b"##", [b"one##", b"two##", b"three"]),
        ],
    )
    def test_basic_split_binaryio(
        self,
        data,
        delim,
        expected,
    ):
        bio = io.BytesIO(data)
        result = list(splitlines_bytes(bio, delim=delim))
        assert result == expected


class TestCommentStripping:
    """Test comment_marker functionality"""

    @pytest.mark.parametrize(
        "data,delim,comment,expected",
        [
            (b"a#comment\nb\nc", b"\n", b"#", [b"a\n", b"b\n", b"c"]),
            (b"a #comment\nb\nc", b"\n", b"#", [b"a \n", b"b\n", b"c"]),
            (b"#full comment\ndata\n", b"\n", b"#", [b"\n", b"data\n"]),
            (b"a//comment\nb", b"\n", b"//", [b"a\n", b"b"]),
            (b"one##comment##two\n", b"\n", b"##", [b"one\n"]),
            # comment_marker can be in delim
            (b"payload###comment##next", b"##", b"#", [b"payload##", b"##", b"next"]),
        ],
    )
    def test_comment_stripping(
        self,
        data,
        delim,
        comment,
        expected,
    ):
        result = list(splitlines_bytes(data, delim=delim, comment_marker=comment))
        assert result == expected

    def test_comment_preserves_delimiter(self):
        """When comment is removed, delimiter should be preserved"""
        data = b"a#comment\nb#comment\n"
        result = list(splitlines_bytes(data, delim=b"\n", comment_marker=b"#"))
        assert result == [b"a\n", b"b\n"]
        # Ensure delimiters are present
        assert all(line.endswith(b"\n") for line in result)


class TestWhitespaceStripping:
    """Test whitespace stripping in various combinations"""

    @pytest.mark.parametrize(
        "data,strip_leading,strip_trailing,expected",
        [
            (b"  a\n  b\n", True, False, [b"a\n", b"b\n"]),
            (b"a  \nb  \n", False, True, [b"a\n", b"b\n"]),
            (b"  a  \n  b  \n", True, True, [b"a\n", b"b\n"]),
            (b"  \n  \n", True, False, [b"\n", b"\n"]),
            (b"  \n  \n", False, True, [b"\n", b"\n"]),  # re_add_delim keeps \n
            (b"  \n  \n", True, True, [b"\n", b"\n"]),  # re_add_delim still keeps \n
            (b"\t\ta\t\t\n", True, True, [b"a\n"]),
            (b" \t\r\na\n", True, False, [b"\n", b"a\n"]),  # \r\n splits on \n only
        ],
    )
    def test_whitespace_stripping(
        self,
        data,
        strip_leading,
        strip_trailing,
        expected,
    ):
        result = list(
            splitlines_bytes(
                data,
                delim=b"\n",
                strip_leading_whitespace=strip_leading,
                strip_trailing_whitespace=strip_trailing,
            )
        )
        assert result == expected

    def test_whitespace_with_non_newline_delim(self):
        data = b"  a  ##  b  ##"
        result = list(
            splitlines_bytes(
                data,
                delim=b"##",
                strip_leading_whitespace=True,
                strip_trailing_whitespace=True,
            )
        )
        # strip_trailing removes trailing whitespace, but spaces before ## remain
        # because ## is not whitespace, so rstrip() is called which keeps internal spaces
        assert result == [b"a  ##", b"b  ##"]


class TestReAddDelimLogic:
    """Test the complex re_add_delim logic when delimiter is in strip_bytes"""

    @pytest.mark.parametrize("delim", [b"\n", b"\r", b"\t", b" ", b"\x0b", b"\x0c"])
    def test_whitespace_delimiters_stripped_and_readded(self, delim):
        """When delim is whitespace, stripping should re-add it"""
        data = b"a" + delim + b"b" + delim
        result = list(
            splitlines_bytes(data, delim=delim, strip_trailing_whitespace=True)
        )
        # Should strip and re-add delimiter
        assert result == [b"a" + delim, b"b" + delim]

    def test_newline_delimiter_with_trailing_strip(self):
        """Specific test for newline with trailing whitespace"""
        data = b"a  \nb  \n"
        result = list(
            splitlines_bytes(data, delim=b"\n", strip_trailing_whitespace=True)
        )
        assert result == [b"a\n", b"b\n"]
        assert all(line.endswith(b"\n") for line in result)

    def test_space_delimiter_with_trailing_strip(self):
        """Space as delimiter should be re-added after strip"""
        data = b"a b c "
        result = list(
            splitlines_bytes(data, delim=b" ", strip_trailing_whitespace=True)
        )
        assert result == [b"a ", b"b ", b"c "]

    def test_non_whitespace_delimiter_not_readded(self):
        """Non-whitespace delimiters shouldn't be re-added after rstrip"""
        data = b"a  ##b  ##"
        result = list(
            splitlines_bytes(data, delim=b"##", strip_trailing_whitespace=True)
        )
        # rstrip() doesn't strip the delimiter or spaces before it
        assert result == [b"a  ##", b"b  ##"]


class TestCombinedFeatures:
    """Test combinations of comment stripping and whitespace handling"""

    def test_comment_and_whitespace_stripping(self):
        data = b"  a  #comment\n  b  #comment\n"
        result = list(
            splitlines_bytes(
                data,
                delim=b"\n",
                comment_marker=b"#",
                strip_leading_whitespace=True,
                strip_trailing_whitespace=True,
            )
        )
        assert result == [b"a\n", b"b\n"]

    def test_empty_after_comment_removal(self):
        data = b"#comment\na\n#comment\n"
        result = list(
            splitlines_bytes(
                data, delim=b"\n", comment_marker=b"#", strip_leading_whitespace=True
            )
        )
        assert result == [b"\n", b"a\n", b"\n"]

    def test_empty_after_comment_removal_with_trailing_strip(self):
        data = b"#comment\na\n#comment\n"
        result = list(
            splitlines_bytes(
                data, delim=b"\n", comment_marker=b"#", strip_trailing_whitespace=True
            )
        )
        # Whitespace delimiters are re-added, so comment-only lines produce b'\n'
        assert result == [b"\n", b"a\n", b"\n"]


class TestBinaryIOStreaming:
    """Test streaming behavior with BinaryIO objects"""

    @pytest.mark.parametrize("chunk_size", [1, 2, 5, 10, 100])
    def test_various_chunk_sizes(self, chunk_size):
        data = b"a\nb\nc\nd\ne\nf\n"
        bio = io.BytesIO(data)
        result = list(splitlines_bytes(bio, delim=b"\n", chunk_size=chunk_size))
        assert result == [b"a\n", b"b\n", b"c\n", b"d\n", b"e\n", b"f\n"]

    def test_delimiter_spanning_chunks(self):
        """Test delimiter that spans across chunk boundaries"""
        data = b"abc##def##ghi"
        bio = io.BytesIO(data)
        result = list(splitlines_bytes(bio, delim=b"##", chunk_size=4))
        assert result == [b"abc##", b"def##", b"ghi"]

    def test_large_data_streaming(self):
        """Test with larger data to ensure buffering works"""
        data = b"\n".join(b"line%d" % i for i in range(1000)) + b"\n"
        bio = io.BytesIO(data)
        result = list(splitlines_bytes(bio, delim=b"\n", chunk_size=100))
        assert len(result) == 1000
        assert result[0] == b"line0\n"
        assert result[-1] == b"line999\n"


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_empty_delimiter_raises(self):
        with pytest.raises(ValueError, match="delim must not be empty"):
            list(splitlines_bytes(b"data", delim=b""))

    def test_none_delimiter_raises(self):
        with pytest.raises(ValueError, match="delim must not be empty"):
            list(splitlines_bytes(b"data", delim=None))

    def test_empty_comment_marker_raises(self):
        with pytest.raises(ValueError, match="comment_marker must not be empty"):
            list(splitlines_bytes(b"data", delim=b"\n", comment_marker=b""))

    def test_comment_marker_not_bytes_raises(self):
        with pytest.raises(TypeError, match="comment_marker must be bytes or None"):
            list(splitlines_bytes(b"data", delim=b"\n", comment_marker="#"))

    def test_comment_marker_equals_delim_raises(self):
        with pytest.raises(ValueError, match="comment_marker can not match delim"):
            list(splitlines_bytes(b"data", delim=b"#", comment_marker=b"#"))

    def test_delim_in_comment_marker_raises(self):
        """delim contained in comment_marker should raise"""
        with pytest.raises(
            ValueError, match="delim must not be contained in comment_marker"
        ):
            list(splitlines_bytes(b"data", delim=b"#", comment_marker=b"##"))

    def test_comment_marker_in_delim_allowed(self):
        """comment_marker contained in delim is allowed"""
        data = b"payload###comment##next"
        result = list(splitlines_bytes(data, delim=b"##", comment_marker=b"#"))
        assert result == [b"payload##", b"##", b"next"]

    def test_multibyte_delimiter(self):
        data = b"one<|>two<|>three"
        result = list(splitlines_bytes(data, delim=b"<|>"))
        assert result == [b"one<|>", b"two<|>", b"three"]

    def test_binary_data_with_nulls(self):
        data = b"a\x00\nb\x00\n"
        result = list(splitlines_bytes(data, delim=b"\n"))
        assert result == [b"a\x00\n", b"b\x00\n"]

    def test_no_trailing_delimiter(self):
        data = b"a\nb\nc"
        result = list(splitlines_bytes(data, delim=b"\n"))
        assert result == [b"a\n", b"b\n", b"c"]
        assert not result[-1].endswith(b"\n")


class TestRealWorldScenarios:
    """Test realistic use cases"""

    def test_config_file_parsing(self):
        """Simulate parsing a config file with comments"""
        data = b"option1=value1\n# this is a comment\noption2=value2  # inline comment\n  \n"
        result = list(
            splitlines_bytes(
                data,
                delim=b"\n",
                comment_marker=b"#",
                strip_leading_whitespace=True,
                strip_trailing_whitespace=True,
            )
        )
        # Comment-only and whitespace-only lines produce b'\n' due to re_add_delim
        assert result == [b"option1=value1\n", b"\n", b"option2=value2\n", b"\n"]

    def test_csv_like_parsing(self):
        """Parse comma-separated data"""
        data = b"a,b,c,d,"
        result = list(splitlines_bytes(data, delim=b","))
        assert result == [b"a,", b"b,", b"c,", b"d,"]

    def test_log_file_processing(self):
        """Process log lines with timestamps"""
        data = b"[INFO] message 1\n[WARN] message 2  \n  [ERROR] message 3\n"
        result = list(
            splitlines_bytes(
                data,
                delim=b"\n",
                strip_leading_whitespace=True,
                strip_trailing_whitespace=True,
            )
        )
        assert result == [
            b"[INFO] message 1\n",
            b"[WARN] message 2\n",
            b"[ERROR] message 3\n",
        ]


class TestDelimiterPreservation:
    """Ensure delimiters are consistently preserved across scenarios"""

    def test_delimiter_always_present_with_comment(self):
        data = b"a#comment\nb#comment\nc\n"
        result = list(splitlines_bytes(data, delim=b"\n", comment_marker=b"#"))
        for line in result:
            if line != result[-1]:  # All but last should have delimiter
                assert line.endswith(b"\n")

    def test_delimiter_preservation_with_all_features(self):
        data = b"  a  #comment\n  b  \n"
        result = list(
            splitlines_bytes(
                data,
                delim=b"\n",
                comment_marker=b"#",
                strip_leading_whitespace=True,
                strip_trailing_whitespace=True,
            )
        )
        assert all(line.endswith(b"\n") for line in result)
