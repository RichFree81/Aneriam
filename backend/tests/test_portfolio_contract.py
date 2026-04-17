"""
Tests for the Portfolio frontend/backend contract fix.

These tests pin down the behaviour resolved by TASK_portfolio_contract_fix:
- description and logo are optional on create.
- description, logo, and updated_at are returned on read.
- updated_at advances past created_at after a PATCH.
- Existing flows (create without the new fields, list, etc.) still work.

They follow the pattern in test_projects.py: use the seeded admin user +
default portfolio, and rely on the rollback fixture in conftest.py.
"""
import time

import pytest
from sqlmodel import select

from app.models import Company, Portfolio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(client, email: str, password: str) -> str:
    resp = client.post("/auth/login", json={"username": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def admin_token(client, db_session):
    """Token for the seeded admin (company admin of demo-company)."""
    return _login(client, "admin@aneriam.com", "adminpass")


@pytest.fixture
def company_a(db_session):
    company = db_session.exec(select(Company).where(Company.slug == "demo-company")).first()
    assert company, "Demo Company not seeded — run seed.py first"
    return company


# ---------------------------------------------------------------------------
# Create — optional description / logo
# ---------------------------------------------------------------------------

def test_create_portfolio_without_description_or_logo(client, admin_token):
    """Baseline: creating with just name + code still works. description/logo are optional."""
    headers = _auth(admin_token)
    payload = {"name": "Portfolio No Extras", "code": "p-no-extras"}

    resp = client.post("/portfolios", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text

    data = resp.json()
    assert data["name"] == "Portfolio No Extras"
    assert data["code"] == "p-no-extras"
    # New fields should be present in the response and default to None.
    assert "description" in data
    assert data["description"] is None
    assert "logo" in data
    assert data["logo"] is None
    assert "updated_at" in data
    assert data["updated_at"] is not None


def test_create_portfolio_with_description_and_logo(client, admin_token):
    """description and logo should persist and be returned when provided on create."""
    headers = _auth(admin_token)
    payload = {
        "name": "Portfolio With Extras",
        "code": "p-with-extras",
        "description": "A portfolio for integration testing.",
        "logo": "https://example.com/logo.png",
    }

    resp = client.post("/portfolios", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text

    data = resp.json()
    assert data["description"] == "A portfolio for integration testing."
    assert data["logo"] == "https://example.com/logo.png"

    # Read back via GET — fields should still be there.
    pid = data["id"]
    resp = client.get(f"/portfolios/{pid}", headers=headers)
    assert resp.status_code == 200, resp.text
    fetched = resp.json()
    assert fetched["description"] == "A portfolio for integration testing."
    assert fetched["logo"] == "https://example.com/logo.png"


# ---------------------------------------------------------------------------
# Read — all new fields present
# ---------------------------------------------------------------------------

def test_read_portfolio_returns_all_contract_fields(client, admin_token):
    """The Portfolio response must carry every field the frontend type declares."""
    headers = _auth(admin_token)
    payload = {"name": "Portfolio Read Check", "code": "p-read-check"}

    create_resp = client.post("/portfolios", json=payload, headers=headers)
    assert create_resp.status_code == 201, create_resp.text
    pid = create_resp.json()["id"]

    resp = client.get(f"/portfolios/{pid}", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Every field the frontend TS type expects.
    expected_keys = {
        "id",
        "company_id",
        "name",
        "code",
        "description",
        "logo",
        "is_active",
        "created_at",
        "updated_at",
        "deleted_at",
    }
    assert expected_keys.issubset(data.keys()), (
        f"Missing keys: {expected_keys - set(data.keys())}"
    )


def test_list_portfolios_returns_all_contract_fields(client, admin_token):
    """The list endpoint also carries the full response shape."""
    headers = _auth(admin_token)
    resp = client.get("/portfolios", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) >= 1

    sample = data[0]
    for key in ("description", "logo", "updated_at"):
        assert key in sample, f"Listing missing {key}"


# ---------------------------------------------------------------------------
# Update — updated_at advances, new fields writable
# ---------------------------------------------------------------------------

def test_patch_portfolio_advances_updated_at(client, admin_token):
    """After a PATCH, updated_at should be strictly greater than created_at."""
    headers = _auth(admin_token)
    create_resp = client.post(
        "/portfolios",
        json={"name": "Portfolio Updatable", "code": "p-updatable"},
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    pid = created["id"]
    created_at = created["created_at"]
    updated_at_initial = created["updated_at"]

    # Tiny sleep so the datetime.now() in the route is measurably later.
    time.sleep(0.05)

    patch_resp = client.patch(
        f"/portfolios/{pid}",
        json={"name": "Portfolio Updatable (renamed)"},
        headers=headers,
    )
    assert patch_resp.status_code == 200, patch_resp.text
    patched = patch_resp.json()

    assert patched["name"] == "Portfolio Updatable (renamed)"
    assert patched["created_at"] == created_at, "created_at must not change on PATCH"
    assert patched["updated_at"] > updated_at_initial, (
        f"updated_at did not advance (was {updated_at_initial}, is {patched['updated_at']})"
    )
    assert patched["updated_at"] > created_at


def test_patch_portfolio_description_and_logo(client, admin_token):
    """PATCH should accept description and logo and persist them."""
    headers = _auth(admin_token)
    create_resp = client.post(
        "/portfolios",
        json={"name": "Portfolio Edit Extras", "code": "p-edit-extras"},
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    pid = create_resp.json()["id"]

    patch_resp = client.patch(
        f"/portfolios/{pid}",
        json={"description": "Now with description.", "logo": "https://example.com/l.png"},
        headers=headers,
    )
    assert patch_resp.status_code == 200, patch_resp.text
    patched = patch_resp.json()
    assert patched["description"] == "Now with description."
    assert patched["logo"] == "https://example.com/l.png"

    # Round-trip via GET.
    resp = client.get(f"/portfolios/{pid}", headers=headers)
    assert resp.status_code == 200, resp.text
    fetched = resp.json()
    assert fetched["description"] == "Now with description."
    assert fetched["logo"] == "https://example.com/l.png"
