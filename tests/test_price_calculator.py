"""Unit tests for processor.price_calculator."""

from decimal import Decimal

import pytest

from core.exceptions import PriceParseError
from processor.price_calculator import build_product_record, calculate_real_price, parse_price


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("149", Decimal("149.00")),
        ("₹ 1,299.50", Decimal("1299.50")),
        ("र 299", Decimal("299.00")),
        ("Rs. 799.00 (Inclusive of all taxes)", Decimal("799.00")),
        ("INR 999", Decimal("999.00")),
        (249.5, Decimal("249.50")),
    ],
)
def test_parse_price_valid(raw, expected):
    assert parse_price(raw) == expected


@pytest.mark.parametrize("raw", ["", "NA", "Free", "0", "-50", "र 100 र 200"])
def test_parse_price_invalid_raises(raw):
    with pytest.raises(PriceParseError):
        parse_price(raw)


def test_calculate_real_price_decimal_precision():
    # 149 * 0.95 = 141.55
    assert calculate_real_price(Decimal("149.00"), Decimal("5")) == Decimal("141.55")
    # 299 * 0.95 = 284.05
    assert calculate_real_price(Decimal("299.00"), Decimal("5")) == Decimal("284.05")
    # 99.99 * (1 - 0.125) = 87.49125 -> 87.49
    assert calculate_real_price(Decimal("99.99"), Decimal("12.5")) == Decimal("87.49")
    # Half-up rounding: 100.05 * 0.90 = 90.045 -> 90.05
    assert calculate_real_price(Decimal("100.05"), Decimal("10")) == Decimal("90.05")


def test_build_product_record_defaults_empty_size_to_na():
    rec = build_product_record(
        sr_no=1,
        name="Herbal Hair Oil,",
        total_price=Decimal("299"),
        discount_percent=Decimal("5"),
        size="  ",
        category_type="Beauty and Cosmetics",
        url="https://striverempire.com/product/detail/herbal-hair-oil-1",
    )
    assert rec.total_price == Decimal("299.00")
    assert rec.real_price == Decimal("284.05")
    assert rec.less_price_display == "5%"
    assert rec.size == "NA"
