"""Project cost hierarchy display helpers."""
from __future__ import annotations


def build_hierarchy(rows) -> list[dict]:
    """Convert aggregated task rows into the project template's hierarchy shape."""

    def _zero() -> dict:
        return {"actual": 0.0, "committed": 0.0, "total": 0.0}

    l1_order: list[str] = []
    l1_map: dict[str, dict] = {}

    for row in rows:
        l1 = row.level1 or "Unallocated"
        l2 = row.level2
        l3 = row.level3
        actual = float(row.actual or 0)
        committed = float(row.committed or 0)
        total = float(row.total or 0)

        if l1 not in l1_map:
            l1_map[l1] = {**_zero(), "direct": None, "l2s": {}, "l2_order": []}
            l1_order.append(l1)
        group1 = l1_map[l1]
        group1["actual"] += actual
        group1["committed"] += committed
        group1["total"] += total

        if l2 is None:
            if group1["direct"] is None:
                group1["direct"] = _zero()
            group1["direct"]["actual"] += actual
            group1["direct"]["committed"] += committed
            group1["direct"]["total"] += total
            continue

        if l2 not in group1["l2s"]:
            group1["l2s"][l2] = {
                **_zero(),
                "name": l2,
                "direct": None,
                "l3_items": [],
                "_item_set": set(),
            }
            group1["l2_order"].append(l2)
        group2 = group1["l2s"][l2]
        group2["actual"] += actual
        group2["committed"] += committed
        group2["total"] += total

        if l3 is None:
            if group2["direct"] is None:
                group2["direct"] = _zero()
            group2["direct"]["actual"] += actual
            group2["direct"]["committed"] += committed
            group2["direct"]["total"] += total
            continue

        if l3 not in group2["_item_set"]:
            group2["l3_items"].append({"name": l3, **_zero()})
            group2["_item_set"].add(l3)
        item = next(i for i in group2["l3_items"] if i["name"] == l3)
        item["actual"] += actual
        item["committed"] += committed
        item["total"] += total

    result = []
    for l1_name in l1_order:
        group1 = l1_map[l1_name]
        l2_groups = []
        for l2_name in group1["l2_order"]:
            group2 = group1["l2s"][l2_name]
            l2_groups.append({
                "name": group2["name"],
                "actual": group2["actual"],
                "committed": group2["committed"],
                "total": group2["total"],
                "direct": group2["direct"],
                "l3_items": group2["l3_items"],
            })
        result.append({
            "name": l1_name,
            "actual": group1["actual"],
            "committed": group1["committed"],
            "total": group1["total"],
            "direct": group1["direct"],
            "l2_groups": l2_groups,
        })
    return result
