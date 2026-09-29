#!/usr/bin/env python3

from __future__ import annotations

from typing import Any

Constraint = dict[str, Any]


def _validate_args(
    *,
    function_name: str,
    args: dict[str, Any],
    constraints: dict[str, Constraint],
) -> None:
    """
    Validate args against constraints keyed by parameter name.

    type: required type or tuple of types
    not_empty: value must not be b""
    nonempty_if_set: value must have len > 0 when not None
    requires: parameter names that must be True when this value is True/set
    requires_if: (param, value) pairs that must hold when this value is True/set
    """
    for param, rules in constraints.items():
        val = args.get(param)

        if "type" in rules and not isinstance(val, rules["type"]):
            raise TypeError(
                f"{function_name}() {param} must be of type {rules['type']}, got {type(val).__name__}"
            )

        if rules.get("not_empty") and val == b"":
            raise ValueError(f"{function_name}() {param} must not be empty")

        if rules.get("nonempty_if_set") and val is not None and len(val) == 0:
            raise ValueError(f"{function_name}() {param} must not be empty if set")

        active = val if isinstance(val, bool) else val is not None

        if active:
            shown = f"{param}=True" if isinstance(val, bool) else param
            for required_param in rules.get("requires", []):
                if args.get(required_param) is not True:
                    raise ValueError(
                        f"{function_name}() {shown} requires {required_param}=True"
                    )
            for dep_param, expected_value in rules.get("requires_if", []):
                if args.get(dep_param) != expected_value:
                    raise ValueError(
                        f"{function_name}() {shown} requires {dep_param}={expected_value}"
                    )
