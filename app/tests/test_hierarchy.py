from __future__ import annotations

from types import SimpleNamespace

from costcontrol.hierarchy import build_hierarchy


def row(level1: str | None, level2: str | None, level3: str | None, actual: float, committed: float, total: float):
    return SimpleNamespace(
        level1=level1,
        level2=level2,
        level3=level3,
        actual=actual,
        committed=committed,
        total=total,
    )


def test_build_hierarchy_preserves_l3_items_and_direct_totals() -> None:
    hierarchy = build_hierarchy([
        row("Construction", "Civil", "Earthworks", 10, 2, 12),
        row("Construction", "Civil", "Concrete", 5, 1, 6),
        row("Construction", "Civil", None, 3, 4, 7),
        row("Construction", None, None, 8, 0, 8),
    ])

    l1 = hierarchy[0]
    assert l1["name"] == "Construction"
    assert l1["actual"] == 26
    assert l1["direct"]["actual"] == 8

    civil = l1["l2_groups"][0]
    assert civil["actual"] == 18
    assert civil["direct"]["total"] == 7
    assert [item["name"] for item in civil["l3_items"]] == ["Earthworks", "Concrete"]
