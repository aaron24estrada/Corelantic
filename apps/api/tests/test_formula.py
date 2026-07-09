from typing import Any

import pytest
from sqlalchemy import ColumnElement, literal_column

from app.query.formula import build_formula
from app.semantic.errors import InvalidFormulaError

_ALLOWED = {"a", "b", "c"}


def _resolve(name: str) -> ColumnElement[Any]:
    return literal_column(f"agg_{name}")


def _sql(expression: str) -> str:
    return " ".join(str(build_formula(expression, _ALLOWED, _resolve).compile()).split())


def test_operators_and_precedence() -> None:
    assert _sql("a + b") == "agg_a + agg_b"
    assert _sql("a - b") == "agg_a - agg_b"
    assert _sql("a * b") == "agg_a * agg_b"
    # Division is guarded against a zero denominator.
    assert "nullif(agg_b" in _sql("a / b")


def test_nested_and_unary() -> None:
    sql = _sql("(a - b) * -c")
    assert "agg_a - agg_b" in sql
    assert "-agg_c" in sql


def test_numeric_literals_bind_as_parameters() -> None:
    # One literal path: numbers never reach the SQL text, only the parameter list.
    assert _sql("a * 100") == "agg_a * :param_1"


def test_division_by_a_constant_is_still_null_guarded() -> None:
    # A zero denominator — literal or named constant — yields NULL, never a runtime error.
    assert "nullif(:param_1, :nullif_1)" in _sql("a / 0")


@pytest.mark.parametrize(
    "expression",
    [
        "a ** b",  # unsupported operator
        "foo(a)",  # call
        "a.b",  # attribute
        "a > b",  # comparison
        "[a, b]",  # list
        "a and b",  # boolean op
        "True",  # boolean literal
    ],
)
def test_disallowed_syntax_raises(expression: str) -> None:
    with pytest.raises(InvalidFormulaError):
        build_formula(expression, _ALLOWED, _resolve)


def test_name_not_in_allowed_is_rejected() -> None:
    with pytest.raises(InvalidFormulaError):
        build_formula("a + z", _ALLOWED, _resolve)
