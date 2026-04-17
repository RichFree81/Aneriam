import pytest
from app.models import User, Company, Portfolio, PortfolioUser
from app.models.enums import UserRole
from app.core.security import get_password_hash
from sqlmodel import Session, select



def test_admin_portfolio_access(client, db_session):
    # Login admin (seeded user — password set in seed.py)
    resp = client.post("/auth/login", json={"username": "admin@aneriam.com", "password": "adminpass"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # List portfolios
    resp = client.get("/portfolios", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    # Check default portfolio exists
    default_p = next((p for p in data if p["code"] == "default-portfolio"), None)
    assert default_p is not None
    
    pid = default_p["id"]
    
    # Get details
    resp = client.get(f"/portfolios/{pid}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == pid

def test_same_company_no_access(client, db_session):
    # Create user in Demo Company but NO portfolio access
    company = db_session.exec(select(Company).where(Company.slug == "demo-company")).first()
    assert company, "Demo Company not found"
    
    email = "user2@test.com"
    pwd = "password123"
    


    user = User(email=email, password_hash=get_password_hash(pwd), company_id=company.id, role=UserRole.USER, is_active=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # Login
    resp = client.post("/auth/login", json={"username": email, "password": pwd})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # List (should be empty)
    resp = client.get("/portfolios", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []
    
    # Get specific (should be 403)
    # Find the default portfolio id first (from DB)
    def_p = db_session.exec(select(Portfolio).where(Portfolio.code == "default-portfolio")).first()
    resp = client.get(f"/portfolios/{def_p.id}", headers=headers)
    assert resp.status_code == 403

def test_cross_company_isolation(client, db_session):
    # Create Company B
    comp_b_slug = "company-b"
    comp_b = db_session.exec(select(Company).where(Company.slug == comp_b_slug)).first()
    if not comp_b:
        comp_b = Company(name="Company B", slug=comp_b_slug)
        db_session.add(comp_b)
        db_session.commit()
        db_session.refresh(comp_b)
    
    # Create User B
    email = "user3@test.com"
    pwd = "password123"
    


    user = User(email=email, password_hash=get_password_hash(pwd), company_id=comp_b.id, role=UserRole.USER, is_active=True)
    db_session.add(user)
    db_session.commit()
    
    # Login
    resp = client.post("/auth/login", json={"username": email, "password": pwd})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try to access Demo Company portfolio
    def_p = db_session.exec(select(Portfolio).where(Portfolio.code == "default-portfolio")).first()
    resp = client.get(f"/portfolios/{def_p.id}", headers=headers)
    # Should be 404 because company mismatch hides it
    assert resp.status_code == 404
