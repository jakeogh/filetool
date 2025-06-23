# conftest.py
import pytest
import sys
from click.testing import Result

_seen_results = []

def _track_result_init(self, *args, **kwargs):
    _original_result_init(self, *args, **kwargs)
    _seen_results.append(self)

_original_result_init = Result.__init__

def pytest_configure(config):
    Result.__init__ = _track_result_init

def pytest_runtest_makereport(item, call):
    if call.when == "call" and call.excinfo:
        for result in _seen_results:
            if not isinstance(result, Result):
                continue
            printed = False
            if hasattr(result, "stdout") and result.stdout:
                print("\n[CliRunner STDOUT]", file=sys.stderr)
                print(result.stdout, file=sys.stderr)
                printed = True
            if hasattr(result, "stderr") and result.stderr:
                print("\n[CliRunner STDERR]", file=sys.stderr)
                print(result.stderr, file=sys.stderr)
                printed = True
            if not printed and result.output:
                print("\n[CliRunner Output (combined)]", file=sys.stderr)
                print(result.output, file=sys.stderr)
        _seen_results.clear()

