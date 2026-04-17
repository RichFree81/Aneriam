import sys
import os
from dotenv import load_dotenv

# Load env vars first
load_dotenv()

# Add backend directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from sqlmodel import Session, select
from app.core.database import engine
from app.models import User, Module, Company, Portfolio, PortfolioUser
from app.core.security import get_password_hash
from app.models.enums import PortfolioRole, UserRole

def seed_company(session: Session) -> Company:
    stmt = select(Company).where(Company.slug == "demo-company")
    company = session.exec(stmt).first()
    if not company:
        print("Seeding company...")
        company = Company(name="Demo Company", slug="demo-company")
        session.add(company)
        session.commit()
        session.refresh(company)
    else:
        print("Company already exists.")
    return company

def seed_portfolio(session: Session, company: Company) -> Portfolio:
    stmt = select(Portfolio).where(Portfolio.code == "default-portfolio")
    portfolio = session.exec(stmt).first()
    if not portfolio:
        print("Seeding portfolio...")
        portfolio = Portfolio(
            company_id=company.id,
            name="Default Portfolio",
            code="default-portfolio"
        )
        session.add(portfolio)
        session.commit()
        session.refresh(portfolio)
    else:
        print("Portfolio already exists.")
    return portfolio

def seed_users(session: Session, company: Company) -> User:
    email = "admin@aneriam.com"
    stmt = select(User).where(User.email == email)
    user = session.exec(stmt).first()
    if not user:
        print(f"Seeding admin user: {email}")
        user = User(
            email=email,
            password_hash=get_password_hash("adminpass"),
            full_name="Admin User",
            role=UserRole.COMPANY_ADMIN,
            is_active=True,
            is_superuser=True,
            company_id=company.id
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    else:
        print("Admin user exists. Updating password and checking company association...")
        user.password_hash = get_password_hash("adminpass")
        if user.company_id is None:
            print("Assigning user to company...")
            user.company_id = company.id
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


def assign_portfolio_access(session: Session, user: User, portfolio: Portfolio):
    stmt = select(PortfolioUser).where(
        PortfolioUser.user_id == user.id, 
        PortfolioUser.portfolio_id == portfolio.id
    )
    access = session.exec(stmt).first()
    if not access:
        print("Assigning portfolio access...")
        access = PortfolioUser(
            company_id=portfolio.company_id,
            portfolio_id=portfolio.id,
            user_id=user.id,
            role=PortfolioRole.PORTFOLIO_ADMIN
        )
        session.add(access)
        session.commit()
    else:
        print("Portfolio access already assigned.")

def seed_modules(session: Session):
    stmt = select(Module)
    existing = session.exec(stmt).first()
    if not existing:
        print("Seeding modules...")
        modules = [
            {"key": "module1", "name": "Module 1", "enabled": False, "description": "Placeholder for Module 1"},
            {"key": "module2", "name": "Module 2", "enabled": False, "description": "Placeholder for Module 2"},
            {"key": "module3", "name": "Module 3", "enabled": False, "description": "Placeholder for Module 3"},
            {"key": "module4", "name": "Module 4", "enabled": False, "description": "Placeholder for Module 4"},
            {"key": "module5", "name": "Module 5", "enabled": False, "description": "Placeholder for Module 5"},
        ]
        for i, m in enumerate(modules):
            mod = Module(**m, sort_order=i)
            session.add(mod)
        session.commit()
    else:
        print("Modules already seeded.")

def main():
    print("Starting database seed...")
    with Session(engine) as session:
        company = seed_company(session)
        portfolio = seed_portfolio(session, company)
        user = seed_users(session, company)
        assign_portfolio_access(session, user, portfolio)
        seed_modules(session)
    print("Seeding complete.")

if __name__ == "__main__":
    main()
