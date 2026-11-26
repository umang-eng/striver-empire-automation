"""Currency parsing and exact Decimal discount price calculation."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re

from core.exceptions import PriceParseError
from core.models import ProductRecord

_CURRENCY_NOISE_RE = re.compile(
    r"(?:₹|र|rs\.?|inr|\$|€|£|\(inclusive of all taxes\))",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def parse_price(raw_value: str | int | float | Decimal) -> Decimal:
    """Parse a price string or numeric value into a positive 2-decimal-place Decimal.

    Never guesses missing prices: raises PriceParseError if invalid or non-positive.
    """
    if isinstance(raw_value, Decimal):
        val = raw_value
    elif isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool):
        val = Decimal(str(raw_value))
    elif isinstance(raw_value, str):
        cleaned = _CURRENCY_NOISE_RE.sub(" ", raw_value).strip()
        matches = _NUMBER_RE.findall(cleaned)
        if not matches:
            raise PriceParseError(f"No numeric price found in {raw_value!r}")
        if len(matches) > 1:
            raise PriceParseError(f"Ambiguous multiple numeric values in price {raw_value!r}")
        numeric_str = matches[0].replace(",", "")
        try:
            val = Decimal(numeric_str)
        except InvalidOperation as exc:
            raise PriceParseError(f"Invalid numeric price {raw_value!r}") from exc
    else:
        raise PriceParseError(f"Unsupported price value type: {type(raw_value).__name__}")

    if not val.is_finite() or val <= Decimal("0"):
        raise PriceParseError(f"Price must be greater than zero, got {val!r}")

    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_real_price(total_price: Decimal, discount_percent: Decimal) -> Decimal:
    """Compute Real Price = Total Price * (1 - discount/100) rounded to 2 decimal places."""
    if total_price <= Decimal("0"):
        raise PriceParseError(f"Total price must be positive, got {total_price}")
    if discount_percent < Decimal("0") or discount_percent > Decimal("100"):
        raise PriceParseError(f"Discount percentage must be in [0, 100], got {discount_percent}")

    multiplier = Decimal("1") - (discount_percent / Decimal("100"))
    return (total_price * multiplier).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_product_record(
    sr_no: int,
    name: str,
    total_price: Decimal,
    discount_percent: Decimal,
    size: str,
    category_type: str,
    url: str,
) -> ProductRecord:
    """Construct a validated ProductRecord with exact Decimal real_price."""
    quantized_total = total_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    real_price = calculate_real_price(quantized_total, discount_percent)
    clean_size = size.strip() if size and size.strip() else "NA"
    return ProductRecord(
        sr_no=sr_no,
        name=name.strip(),
        total_price=quantized_total,
        discount_percent=discount_percent,
        real_price=real_price,
        size=clean_size,
        category_type=category_type,
        url=url,
    )
