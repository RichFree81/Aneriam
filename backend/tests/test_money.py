import pytest
from decimal import Decimal
from pydantic import BaseModel, ValidationError
from app.core.money import Money, quantize_currency

class TestModel(BaseModel):
    amount: Money

def test_money_accepts_valid_types():
    assert TestModel(amount=Decimal("10.50")).amount == Decimal("10.50")
    assert TestModel(amount="10.50").amount == Decimal("10.50")
    assert TestModel(amount=10).amount == Decimal("10")
    # int to decimal conversion may add .0 or not depends on implementation but value equality holds
    
def test_money_rejects_float():
    with pytest.raises(ValidationError) as excinfo:
        TestModel(amount=10.5)
    assert "Float not allowed" in str(excinfo.value)

def test_quantize_currency():
    d = Decimal("10.555")
    q = quantize_currency(d)
    assert q == Decimal("10.56") # Rounds half up
    
    d2 = Decimal("10.554")
    assert quantize_currency(d2) == Decimal("10.55")
