"""
isort:skip_file
"""

from .filetool import append_bytes_to_file as append_bytes_to_file
from .filetool import comment_out_line_in_file as comment_out_line_in_file
from .filetool import ensure_line_in_config_file as ensure_line_in_config_file

from .append_line_to_path import append_line_to_path as append_line_to_path
from .append_bytes_to_path import append_bytes_to_path as append_bytes_to_path

from .cli import cli as cli

# Define public API explicitly
__all__ = [
    "append_line_to_path",
    "append_bytes_to_path",
    "comment_out_line_in_file",
    "cli",
]
