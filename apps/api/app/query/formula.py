"""Compile a derived metric's formula into a SQLAlchemy Core expression tree.

A formula is a deliberately tiny language: component-measure *names*, numeric literals,
and the binary operators ``+ - * /`` (plus unary minus). We parse it with Python's
``ast`` and walk only that allowlist of node types, translating each into a Core column
expression. There is no ``eval`` and no string SQL: an unsupported node, or a name the
caller's resolver rejects, raises ``FormulaError`` instead of reaching the database.

Division is guarded with ``nullif(denominator, 0)`` so a zero denominator yields NULL
rather than a runtime error — the same guard ratio metrics get.
"""

import ast
from collections.abc import Callable
from typing import Any

from sqlalchemy import ColumnElement, func, literal_column

from app.query.errors import FormulaError

# Measure name -> the Core expression for that measure. Supplied by the compiler, which
# also enforces that the name is one of the metric's declared component measures.
Resolver = Callable[[str], ColumnElement[Any]]


def build_formula(expression: str, resolve: Resolver) -> ColumnElement[Any]:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise FormulaError(expression, "not a parseable expression") from exc
    return _eval(tree.body, expression, resolve)


def safe_divide(
    numerator: ColumnElement[Any], denominator: ColumnElement[Any]
) -> ColumnElement[Any]:
    """``numerator / denominator`` with a zero denominator mapped to NULL."""

    return numerator / func.nullif(denominator, 0)


def _eval(node: ast.expr, expression: str, resolve: Resolver) -> ColumnElement[Any]:
    if isinstance(node, ast.Name):
        return resolve(node.id)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        # Reject bools (a subtype of int) — they are not meaningful in a formula.
        if isinstance(node.value, bool):
            raise FormulaError(expression, "boolean literals are not allowed")
        return literal_column(repr(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval(node.operand, expression, resolve)
    if isinstance(node, ast.BinOp):
        left = _eval(node.left, expression, resolve)
        right = _eval(node.right, expression, resolve)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return safe_divide(left, right)
        raise FormulaError(expression, f"operator {type(node.op).__name__} is not allowed")
    raise FormulaError(expression, f"{type(node).__name__} is not allowed")
