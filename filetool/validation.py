#!/usr/bin/env python3
# tab-width:4

"""
Shared validation exception for filetool.
"""

from __future__ import annotations


class ValidationError(ValueError):
    """
    Validation error that can carry both Python API and CLI-friendly messages.

    When raised from standalone functions, can include a CLI-specific message
    that references flag names instead of parameter names.
    """

    def __init__(
        self,
        msg: str,
        cli_msg: str | None = None,
    ):
        super().__init__(msg)
        self.cli_msg = cli_msg
