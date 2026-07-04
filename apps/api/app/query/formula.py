"""Translate a derived metric's formula into a SQLAlchemy Core expression tree.

The grammar itself — which names, literals, and operators are legal — is owned by
``app/semantic/formula.py``; we call its ``validate_formula`` first, so this module only
ever walks an expression that has already been approved. There is no ``eval`` and no
string SQL: names resolve to authored measure expressions, numbers render as literals,
and ``+ - * /`` become Core operators. Division is guarded with ``nullif(denominator, 0)``
so a zero denominator yields NULL rather than a runtime error.
"""

import ast
from collections.abc import Callable
from typing import Any

from sqlalchemy import ColumnElement, func, literal_column

from app.semantic.formula import validate_formula

# Measure name -> the Core expression for that measure, supplied by the compiler.
Resolver = Callable[[str], ColumnElement[Any]]


def build_formula(expression: str, allowed: set[str], resolve: Resolver) -> ColumnElement[Any]:
    validate_formula(expression, allowed)
    tree = ast.parse(expression, mode="eval")
    return _to_core(tree.body, resolve)


def safe_divide(
    numerator: ColumnElement[Any], denominator: ColumnElement[Any]
) -> ColumnElement[Any]:
    """``numerator / denominator`` with a zero denominator mapped to NULL."""

    return numerator / func.nullif(denominator, 0)


def _to_core(node: ast.expr, resolve: Resolver) -> ColumnElement[Any]:
    # validate_formula has already rejected anything off the allowlist, so the branches
    # here mirror it exactly; the final raise is a defensive backstop, not a user path.
    if isinstance(node, ast.Name):
        return resolve(node.id)
    if isinstance(node, ast.Constant):
        return literal_column(repr(node.value))
    if isinstance(node, ast.UnaryOp):
        return -_to_core(node.operand, resolve)
    if isinstance(node, ast.BinOp):
        left = _to_core(node.left, resolve)
        right = _to_core(node.right, resolve)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        return safe_divide(left, right)
    raise AssertionError(f"unvalidated formula node: {type(node).__name__}")  # pragma: no cover
