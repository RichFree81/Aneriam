"""Cost-node tree and amount helpers."""
from __future__ import annotations

from typing import Any


def flatten_cost_nodes(nodes: list[Any], depth: int = 0, ancestor_ids: tuple[int, ...] = ()) -> list[dict]:
    """Flatten a package cost tree into display rows with rolled-up subtotals."""
    rows = []
    for node in sorted(nodes, key=lambda n: n.display_order):
        child_rows = flatten_cost_nodes(node.children, depth + 1, ancestor_ids + (node.id,))

        def _col_total(col: str, n=node, cr=child_rows) -> float:
            own = getattr(n, col) or 0.0
            return own + sum(r["_subtotals"][col] for r in cr if r["node"].parent_id == n.id)

        subtotals = {
            "pre_award": _col_total("pre_award_amount"),
            "contract": _col_total("contract_amount"),
        }
        subtotals["effective"] = (
            subtotals["contract"] if subtotals["contract"]
            else subtotals["pre_award"]
        )

        rows.append({
            "node": node,
            "depth": depth,
            "ancestor_ids": ancestor_ids,
            "_subtotals": subtotals,
        })
        rows.extend(child_rows)
    return rows


def package_effective_total(pkg: Any) -> float:
    """Sum the most mature amount on each item node for one package."""
    if hasattr(pkg, "cost_items") and pkg.cost_items:
        return sum(
            float(item.value or 0)
            for item in pkg.cost_items
            if not getattr(item, "superseded", False)
        )
    total = 0.0
    for node in pkg.cost_nodes:
        if node.is_item:
            value = node.contract_amount or node.pre_award_amount
            if value:
                total += value
    return total


def parse_float(value: str) -> float | None:
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def process_cost_column(unit_str: str, qty_str: str, rate_str: str, amount_str: str):
    """Return (unit, qty, rate, amount) for one package cost column."""
    unit = unit_str.strip() or "Sum"
    if unit in ("Sum", "P.Sum"):
        return unit, None, None, parse_float(amount_str)
    qty = parse_float(qty_str)
    rate = parse_float(rate_str)
    return unit, qty, rate, (qty or 0.0) * (rate or 0.0)
