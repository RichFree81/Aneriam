"""
Tests for the /projects/portfolios/{portfolio_id}/projects endpoints.

Covers:
- Happy-path CRUD for an authorised user
- C-1 regression: cross-tenant project access is blocked
- Negative-path: unauthenticated, invalid token, revoked token
"""
import pytest
from sqlmodel import select

from app.models import Company, Portfolio, PortfolioUser, Project, User
from app.models.enums import PortfolioRole, UserRole
from app.core.security import get_password_hash


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
def company_a(db_session):
    company = db_session.exec(select(Company).where(Company.slug == "demo-company")).first()
    assert company, "Demo Company not seeded — run seed.py first"
    return company


@pytest.fixture
def portfolio_a(db_session, company_a):
    portfolio = db_session.exec(
        select(Portfolio).where(Portfolio.code == "default-portfolio")
    ).first()
    assert portfolio, "Default portfolio not seeded — run seed.py first"
    return portfolio


@pytest.fixture
def admin_token(client, db_session):
    """Token for the seeded admin user (has company-admin access to demo-company)."""
    return _login(client, "admin@aneriam.com", "adminpass")


@pytest.fixture
def company_b_user(client, db_session):
    """A user in a *different* company with no access to company_a portfolios."""
    slug = "company-b-projects-test"
    comp_b = db_session.exec(select(Company).where(Company.slug == slug)).first()
    if not comp_b:
        comp_b = Company(name="Company B (Projects Test)", slug=slug)
        db_session.add(comp_b)
        db_session.commit()
        db_session.refresh(comp_b)

    email = "userb_projects@test.com"
    user = db_session.exec(select(User).where(User.email == email)).first()
    if not user:
        user = User(
            email=email,
            password_hash=get_password_hash("password123"),
            company_id=comp_b.id,
            role=UserRole.USER,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

    token = _login(client, email, "password123")
    return {"user": user, "token": token, "company": comp_b}


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

def test_create_and_list_projects(client, db_session, admin_token, portfolio_a):
    """Admin can create a project and then retrieve it from the list."""
    pid = portfolio_a.id
    headers = _auth(admin_token)

    payload = {"name": "Test Project Alpha", "description": "Integration test project"}
    resp = client.post(f"/projects/portfolios/{pid}/projects", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["name"] == "Test Project Alpha"
    assert created["portfolio_id"] == pid

    # List projects — should include the newly created one
    resp = client.get(f"/projects/portfolios/{pid}/projects", headers=headers)
    assert resp.status_code == 200, resp.text
    names = [p["name"] for p in resp.json()]
    assert "Test Project Alpha" in names


def test_create_project_sets_company_id(client, db_session, admin_token, portfolio_a):
    """Created project should have company_id matching the portfolio's company."""
    pid = portfolio_a.id
    headers = _auth(admin_token)

    resp = client.post(
        f"/projects/portfolios/{pid}/projects",
        json={"name": "Company ID Check Project"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    project = db_session.get(Project, data["id"])
    assert project is not None
    assert project.company_id == portfolio_a.company_id


# ---------------------------------------------------------------------------
# Multi-tenancy (C-1 regression) tests
# ---------------------------------------------------------------------------

def test_cross_tenant_cannot_read_projects(client, db_session, company_b_user, portfolio_a):
    """
    C-1 regression: a user from Company B must NOT be able to list projects
    in Company A's portfolio, even if they know the portfolio_id.
    """
    pid = portfolio_a.id
    headers = _auth(company_b_user["token"])

    resp = client.get(f"/projects/portfolios/{pid}/projects", headers=headers)
    # get_valid_portfolio hides cross-company portfolios as 404
    assert resp.status_code == 404, resp.text


def test_cross_tenant_cannot_create_project(client, db_session, company_b_user, portfolio_a):
    """
    C-1 regression: a user from Company B must NOT be able to create a project
    in Company A's portfolio.
    """
    pid = portfolio_a.id
    headers = _auth(company_b_user["token"])

    resp = client.post(
        f"/projects/portfolios/{pid}/projects",
        json={"name": "Malicious Cross-Tenant Project"},
        headers=headers,
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Negative-path tests
# ---------------------------------------------------------------------------

def test_unauthenticated_cannot_list_projects(client, portfolio_a):
    """No token → 401 Unauthorized."""
    resp = client.get(f"/projects/portfolios/{portfolio_a.id}/projects")
    assert resp.status_code == 401


def test_invalid_token_rejected(client, portfolio_a):
    """Malformed / tampered token → 401."""
    headers = {"Authorization": "Bearer this.is.not.a.valid.jwt"}
    resp = client.get(f"/projects/portfolios/{portfolio_a.id}/projects", headers=headers)
    assert resp.status_code == 401


def test_project_create_rejects_short_name(client, db_session, admin_token, portfolio_a):
    """Empty name should be rejected (min_length=1 on ProjectCreate.name)."""
    headers = _auth(admin_token)
    resp = client.post(
        f"/projects/portfolios/{portfolio_a.id}/projects",
        json={"name": ""},
        headers=headers,
    )
    assert resp.status_code == 422  # Pydantic validation error


def test_logout_invalidates_token(client, db_session, admin_token, portfolio_a):
    """After logout, the access token should be rejected."""
    headers = _auth(admin_token)

    # Confirm token is valid before logout
    resp = client.get(f"/projects/portfolios/{portfolio_a.id}/projects", headers=headers)
    assert resp.status_code == 200

    # Logout
    resp = client.post("/auth/logout", headers=headers)
    assert resp.status_code == 204

    # Token should now be rejected
    resp = client.get(f"/projects/portfolios/{portfolio_a.id}/projects", headers=headers)
    assert resp.status_code == 401


def test_refresh_token_flow(client, db_session, portfolio_a):
    """
    After login, the refresh token can be used to obtain a new access token,
    and the refreshed access token works for subsequent requests.
    """
    login_resp = client.post(
        "/auth/login", json={"username": "admin@aneriam.com", "password": "adminpass"}
    )
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert "refresh_token" in data

    refresh_resp = client.post(
        "/auth/refresh", json={"refresh_token": data["refresh_token"]}
    )
    assert refresh_resp.status_code == 200
    new_data = refresh_resp.json()
    assert "access_token" in new_data
    assert new_data["access_token"] != data["access_token"]

    # New access token works
    headers = _auth(new_data["access_token"])
    resp = client.get(f"/projects/portfolios/{portfolio_a.id}/projects", headers=headers)
    assert resp.status_code == 200


def test_refresh_token_rotation(client, db_session):
    """
    Refresh token rotation: using the same refresh token twice should fail
    on the second attempt (it was revoked on first use).
    """
    login_resp = client.post(
        "/auth/login", json={"username": "admin@aneriam.com", "password": "adminpass"}
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    # First use — OK
    resp1 = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp1.status_code == 200

    # Second use of the same refresh token — must be rejected
    resp2 = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp2.status_code == 401
