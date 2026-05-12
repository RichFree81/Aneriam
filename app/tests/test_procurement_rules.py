from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from costcontrol import rto, tender
from costcontrol.routes import procurement


def test_internal_package_is_blocked_from_procurement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        procurement,
        "get_package_or_404",
        lambda _db, _project_number, _package_number: SimpleNamespace(is_external=False),
    )

    with pytest.raises(HTTPException) as exc_info:
        procurement._get_external_package_or_404(object(), "P-001", "PKG-001")

    assert exc_info.value.status_code == 404


def test_external_package_is_allowed_for_procurement(monkeypatch: pytest.MonkeyPatch) -> None:
    package = SimpleNamespace(is_external=True)
    monkeypatch.setattr(
        procurement,
        "get_package_or_404",
        lambda _db, _project_number, _package_number: package,
    )

    assert procurement._get_external_package_or_404(object(), "P-001", "PKG-001") is package


def test_rto_workflow_and_match_scoring() -> None:
    assert rto.can_transition(rto.STATUS_DRAFT, rto.STATUS_SUBMITTED)
    assert not rto.can_transition(rto.STATUS_DRAFT, rto.STATUS_ISSUED)
    assert rto.can_delete(rto.STATUS_CANCELLED)

    candidate = SimpleNamespace(
        vendor_name="12345 ACME Ltd",
        total_amount=1000,
        request_date=date(2026, 5, 1),
        status=rto.STATUS_APPROVED,
    )
    score = rto.score_match(
        {"vendor": "ACME LTD", "order_amount": 1005, "first_date": date(2026, 5, 1)},
        candidate,
    )
    assert score == 90


def test_tender_workflow_and_weighted_score() -> None:
    assert tender.can_transition(tender.STATUS_DRAFT, tender.STATUS_ISSUED)
    assert not tender.can_transition(tender.STATUS_AWARDED, tender.STATUS_CANCELLED)
    assert tender.can_delete(tender.STATUS_DRAFT)
    assert not tender.can_delete(tender.STATUS_ISSUED)

    assert tender.weighted_score({1: 80, 2: 100}, {1: 25, 2: 75}) == 95
    assert tender.weighted_score({1: 80}, {1: 0}) is None
