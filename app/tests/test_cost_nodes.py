from __future__ import annotations

from costcontrol.cost_nodes import parse_float, process_cost_column


def test_parse_float_handles_invalid_input() -> None:
    assert parse_float("12.5") == 12.5
    assert parse_float("") is None
    assert parse_float("not a number") is None


def test_process_cost_column_sum_uses_entered_amount() -> None:
    assert process_cost_column("Sum", "2", "10", "35") == ("Sum", None, None, 35.0)


def test_process_cost_column_quantity_rate_calculates_amount() -> None:
    assert process_cost_column("m", "3", "4.5", "999") == ("m", 3.0, 4.5, 13.5)
