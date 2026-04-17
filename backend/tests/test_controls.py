import pytest
from decimal import Decimal
from sqlmodel import Session
from app.models.financial_note import FinancialNote
from app.models.audit_log import AuditLog
from app.models.enums import WorkflowStatus
from app.core import audit, audit_log, workflow
from fastapi import HTTPException



from app.models.user import User
from app.models.company import Company
from app.models.portfolio import Portfolio
from sqlmodel import select

@pytest.fixture
def setup_data(db_session):
    # Ensure company exists
    company = Company(name="Test Company", slug="test-company-controls")
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    
    # Ensure portfolio exists
    portfolio = Portfolio(name="Test Portfolio", code="test-portfolio-controls", company_id=company.id)
    db_session.add(portfolio)
    db_session.commit()
    db_session.refresh(portfolio)
    
    # Ensure users exist
    user1 = User(email="user1@controls.com", password_hash="hash", company_id=company.id)
    db_session.add(user1)
    db_session.commit()
    db_session.refresh(user1)

    user2 = User(email="user2@controls.com", password_hash="hash", company_id=company.id)
    db_session.add(user2)
    db_session.commit()
    db_session.refresh(user2)
    
    return {"company": company, "portfolio": portfolio, "user1": user1, "user2": user2}

def test_audit_mixin(db_session, setup_data):
    u1 = setup_data["user1"]
    u2 = setup_data["user2"]
    p = setup_data["portfolio"]
    
    # Setup
    note = FinancialNote(content="Test Audit", amount=Decimal("100.00"), portfolio_id=p.id, company_id=p.company_id)
    
    # Test Create Helper
    audit.apply_audit_create(note, user_id=u1.id)
    db_session.add(note)
    db_session.commit()
    db_session.refresh(note)
    
    assert note.created_by_user_id == u1.id
    assert note.created_at is not None
    assert note.updated_at is not None

    # Test Update Helper
    old_updated_at = note.updated_at
    audit.apply_audit_update(note, user_id=u2.id)
    db_session.add(note)
    db_session.commit()
    db_session.refresh(note)
    
    assert note.updated_by_user_id == u2.id
    assert note.updated_at > old_updated_at

def test_audit_log(db_session, setup_data):
    u1 = setup_data["user1"]
    c = setup_data["company"]
    
    # Test Logging
    log = audit_log.log_change(
        session=db_session,
        company_id=c.id,
        actor_user_id=u1.id,
        entity_type="FinancialNote",
        entity_id="999",
        action="CREATE",
        after={"content": "Test"}
    )
    db_session.commit()
    
    saved = db_session.get(AuditLog, log.id)
    assert saved is not None
    assert saved.entity_type == "FinancialNote"
    assert saved.action == "CREATE"
    assert saved.company_id == c.id

def test_workflow_locking(db_session, setup_data):
    p = setup_data["portfolio"]
    u1 = setup_data["user1"]
    
    note = FinancialNote(content="Lock me", amount=Decimal("50.00"), portfolio_id=p.id, company_id=p.company_id)
    db_session.add(note)
    db_session.commit()
    
    # 1. Assert mutable when DRAFT (default)
    workflow.assert_mutable(note) # Should not raise
    
    # 2. Lock it
    workflow.set_status(note, WorkflowStatus.LOCKED, user_id=u1.id)
    db_session.add(note)
    db_session.commit()
    db_session.refresh(note)
    
    assert note.status == WorkflowStatus.LOCKED
    assert note.locked_at is not None
    assert note.locked_by_user_id == u1.id
    
    # 3. Try to assert mutable (should fail)
    with pytest.raises(HTTPException) as exc:
        workflow.assert_mutable(note)
    assert "cannot be modified" in str(exc.value)

    # 4. Unlock (move to Draft)
    workflow.set_status(note, WorkflowStatus.DRAFT, user_id=u1.id)
    db_session.add(note)
    db_session.commit()
    db_session.refresh(note)
    
    assert note.status == WorkflowStatus.DRAFT
    assert note.locked_at is None
    workflow.assert_mutable(note) # Should pass
