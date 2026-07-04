from typing import Any

import pytest
from sqlalchemy import ColumnElement, literal_column

from app.query.errors import FormulaError
from app.query.formula import build_formula


def _resolve(name: str) -> ColumnElement[Any]:
    known = {"a", "b", "c"}
    if name not in known:
        raise FormulaError(name, f"unknown measure {name!r}")
    return literal_column(f"agg_{name}")


def _sql(expression: str) -> str:
    return " ".join(str(build_formula(expression, _resolve).compile()).split())


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


def test_numeric_literals_render_inline() -> None:
    assert _sql("a * 100") == "agg_a * 100"


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
    with pytest.raises(FormulaError):
        build_formula(expression, _resolve)


def test_unknown_name_is_rejected_by_the_resolver() -> None:
    with pytest.raises(FormulaError):
        build_formula("a + z", _resolve)
