
import os
import tempfile
from pathlib import Path
from click.testing import CliRunner
import pytest
from filetool.cli import cli

@pytest.fixture
def tmpfile(tmp_path):
    return tmp_path / "file.txt"

def read_file(path):
    return path.read_bytes()

def test_basic_append(tmpfile):
    runner = CliRunner()
    result = runner.invoke(cli, ["append", "--path", str(tmpfile), "--create", "hello"])
    assert result.exit_code == 0
    assert read_file(tmpfile) == b"hello\n"

def test_multiple_lines(tmpfile):
    runner = CliRunner()
    result = runner.invoke(cli, ["append", "--path", str(tmpfile), "--create", "a", "b"])
    assert result.exit_code == 0
    assert read_file(tmpfile) == b"a\nb\n"

def test_unique_append(tmpfile):
    tmpfile.write_text("unique\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["append", "--path", str(tmpfile), "--unique", "--line-ending-hex", "0a", "unique"])
    assert result.exit_code == 0
    assert read_file(tmpfile) == b"unique\n"

def test_unique_ignore_whitespace(tmpfile):
    tmpfile.write_text("  hello  \n")
    runner = CliRunner()
    result = runner.invoke(cli, ["append", "--path", str(tmpfile), "--unique", "--line-ending-hex", "0a", "--ignore-leading-whitespace", "--ignore-trailing-whitespace", "hello"])
    assert result.exit_code == 0
    assert read_file(tmpfile) == b"  hello  \n"


def test_comment_marker(tmpfile):
    tmpfile.write_text("abc # comment\n")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "append",
            "--path", str(tmpfile),
            "--unique",
            "--line-ending-hex", "0a",
            "--comment-marker", "#",
            "abc"
        ]
    )
    assert result.exit_code == 0
    # Since "abc" is not equal to "abc" after comment stripping, it should be appended
    assert read_file(tmpfile) == b"abc # comment\nabc\n"

def test_bytes_from_path(tmpfile, tmp_path):
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"binary\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["append", "--path", str(tmpfile), "--bytes-from-path", str(payload), "--create", "--unique", "--line-ending-hex", "0a"])
    assert result.exit_code == 0
    assert read_file(tmpfile) == b"binary\n"

def test_do_not_append_newline(tmpfile):
    runner = CliRunner()
    result = runner.invoke(cli, ["append", "--path", str(tmpfile), "--create", "--do-not-append-newline", "no-newline"])
    assert result.exit_code == 0
    assert read_file(tmpfile) == b"no-newline"

def test_hex_input(tmpfile):
    runner = CliRunner()
    result = runner.invoke(cli, ["append", "--path", str(tmpfile), "--create", "--hex-input", "68656c6c6f"])
    assert result.exit_code == 0
    assert read_file(tmpfile) == b"hello\n"

def test_unlink_first(tmpfile):
    tmpfile.write_text("abc")
    runner = CliRunner()
    result = runner.invoke(cli, ["append", "--path", str(tmpfile), "--unlink-first", "--unique", "--line-ending-hex", "0a", "new"])
    assert result.exit_code == 0
    assert read_file(tmpfile) == b"new\n"

def test_make_parents(tmp_path):
    file_path = tmp_path / "nested" / "file.txt"
    runner = CliRunner()
    result = runner.invoke(cli, ["append", "--path", str(file_path), "--create", "--make-parents", "deep"])
    assert result.exit_code == 0
    assert file_path.read_bytes() == b"deep\n"

def test_dry_run(tmpfile):
    runner = CliRunner()
    result = runner.invoke(cli, ["append", "--path", str(tmpfile), "--create", "--dry-run", "test"])
    assert result.exit_code == 0
    assert not tmpfile.exists()

def test_error_no_input(tmpfile):
    runner = CliRunner()
    result = runner.invoke(cli, ["append", "--path", str(tmpfile)])
    assert result.exit_code != 0
    assert "At least one of LINE or --bytes-from-path" in result.output

def test_error_conflict_bytes_and_positional(tmpfile, tmp_path):
    payload = tmp_path / "payload"
    payload.write_text("abc")
    runner = CliRunner()
    result = runner.invoke(cli, ["append", "--path", str(tmpfile), "--bytes-from-path", str(payload), "abc"])
    assert result.exit_code != 0

def test_error_make_parents_without_create(tmpfile):
    runner = CliRunner()
    result = runner.invoke(cli, ["append", "--path", str(tmpfile), "--make-parents", "abc"])
    assert result.exit_code != 0

def test_error_unlink_first_without_unique(tmpfile):
    runner = CliRunner()
    result = runner.invoke(cli, ["append", "--path", str(tmpfile), "--unlink-first", "abc"])
    assert result.exit_code != 0
