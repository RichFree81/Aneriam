from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Annotated
from pydantic import BeforeValidator, WithJsonSchema

def validate_no_float(v: Any) -> Decimal:
    """
    Validator to reject float values for monetary fields.
    Accepts: Decimal, str, int.
    Rejects: float.
    """
    if isinstance(v, float):
        raise ValueError("Float not allowed for monetary values. Use Decimal, str, or int.")
    try:
        if isinstance(v, Decimal):
             return v
        return Decimal(v)
    except (TypeError, InvalidOperation):
        raise ValueError("Invalid decimal value")

# Custom Type for Money to be used in Pydantic models
Money = Annotated[Decimal, BeforeValidator(validate_no_float), WithJsonSchema({"type": "string", "format": "decimal"})]

def quantize_currency(amount: Decimal, places: int = 2) -> Decimal:
    """
    Standard currency quantization (rolling round half up).
    Default is 2 decimal places.
    """
    return amount.quantize(Decimal(10) ** -places, rounding=ROUND_HALF_UP)
