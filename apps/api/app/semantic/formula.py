"""Validate a derived metric's formula — the grammar authority, load-time and pure.

A formula is a deliberately tiny language: component-measure *names*, numeric literals,
and the binary operators ``+ - * /`` (plus unary minus). This module parses it with
Python's ``ast`` and confirms every node is on that allowlist and every name is one of
the metric's declared measures — raising ``InvalidFormulaError`` otherwise, at registry
load, before any query runs.

It is the single authority on what a formula may contain. ``app/query/formula.py`` calls
``validate_formula`` before translating the same expression into a SQLAlchemy Core tree,
so the SQL builder only ever walks an already-approved expression. Kept SQLAlchemy-free
so the loader can use it without ``query`` depending backwards on ``semantic``.
"""

import ast
import math

from app.semantic.errors import InvalidFormulaError

ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)


def validate_formula(expression: str, allowed: set[str]) -> None:
    """Raise ``InvalidFormulaError`` unless the formula is on the allowlist.

    ``allowed`` is the set of measure names the formula may reference.
    """

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise InvalidFormulaError(expression, "not a parseable expression") from exc
    _check(tree.body, expression, allowed)


def _check(node: ast.expr, expression: str, allowed: set[str]) -> None:
    if isinstance(node, ast.Name):
        if node.id not in allowed:
            raise InvalidFormulaError(
                expression, f"{node.id!r} is not one of the metric's measures {sorted(allowed)}"
            )
        return
    if isinstance(node, ast.Constant):
        # bool is a subtype of int — exclude it; only finite numbers are meaningful.
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise InvalidFormulaError(expression, "only numeric literals are allowed")
        if isinstance(node.value, float) and not math.isfinite(node.value):
            raise InvalidFormulaError(expression, "non-finite numeric literal")
        return
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        _check(node.operand, expression, allowed)
        return
    if isinstance(node, ast.BinOp) and isinstance(node.op, ALLOWED_BINOPS):
        _check(node.left, expression, allowed)
        _check(node.right, expression, allowed)
        return
    raise InvalidFormulaError(expression, f"{type(node).__name__} is not allowed")
