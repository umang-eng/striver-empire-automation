"""Unit tests for processor.message_parser and filename convention."""

from decimal import Decimal

import pytest

from core.exceptions import TaskParseError
from core.models import SubcategoryTarget
from main import resolve_output_paths
from processor.message_parser import (
    build_output_stem,
    parse_task_message,
    resolve_filename_category_label,
)


@pytest.mark.parametrize(
    "raw,expected_cat,expected_disc",
    [
        ("women 25%", "Women", Decimal("25")),
        ("men 10%", "Men", Decimal("10")),
        ("beauty and cosmetics 5%", "Beauty and Cosmetics", Decimal("5")),
        ("accessories 15%", "Accessories", Decimal("15")),
        ("winter 20%", "Winter", Decimal("20")),
        ("home and living 10%", "Home and Living", Decimal("10")),
        ("women shirt 5%", "Women Shirt", Decimal("5")),
        ("men formal pants 12.5%", "Men Formal Pants", Decimal("12.5")),
        ("  WOMEN'S   SHIRT   5.5% ", "Women's Shirt", Decimal("5.5")),
        ("Formal Pants - 0%", "Formal Pants", Decimal("0")),
        ("beauty and cosmetics 10 percent", "Beauty and Cosmetics", Decimal("10")),
    ],
)
def test_parse_valid_task_messages(raw, expected_cat, expected_disc):
    task = parse_task_message(raw)
    assert task.category == expected_cat
    assert task.discount_percent == expected_disc


def test_parse_zero_discount_display():
    task = parse_task_message("bedsheets 0%")
    assert task.discount_percent == Decimal("0")
    assert task.discount_display == "0%"


@pytest.mark.parametrize(
    "bad_input",
    [
        "",
        "   ",
        "women",
        "beauty and cosmetics",
        "25%",
        "  5% ",
        "women 100%",
        "women 150%",
        "women -5%",
    ],
)
def test_parse_invalid_messages_raise(bad_input):
    with pytest.raises(TaskParseError):
        parse_task_message(bad_input)


@pytest.mark.parametrize(
    "raw,expected_stem",
    [
        ("women 5%", "Women's 5%"),
        ("women 10%", "Women's 10%"),
        ("men 5%", "Men's 5%"),
        ("beauty and cosmetics 5%", "Beauty and Cosmetics 5%"),
        ("accessories 10%", "Accessories 10%"),
        ("winter 15%", "Winter 15%"),
        ("home and living 5%", "Home & Living 5%"),
        ("men formal pants 12.5%", "Men's Formal Pants 12.5%"),
    ],
)
def test_build_output_stem_matches_required_format(raw, expected_stem):
    task = parse_task_message(raw)
    assert build_output_stem(task) == expected_stem


def test_resolve_filename_category_label_with_subcategories():
    task = parse_task_message("women formal pant 5%")
    sub = SubcategoryTarget(
        name="Formal Pant",
        url="https://striverempire.com/product/list/formal-pant",
        parent_name="Women's",
    )
    label = resolve_filename_category_label(task, targets=[sub], is_parent_category=False)
    assert build_output_stem(task, display_category=label) == "Women's Formal Pant 5%"

    task_jeans = parse_task_message("women jeans 5%")
    sub_jeans = SubcategoryTarget(
        name="Women Jeans",
        url="https://striverempire.com/product/list/women-jeans",
        parent_name="Women's",
    )
    label_jeans = resolve_filename_category_label(task_jeans, targets=[sub_jeans], is_parent_category=False)
    assert build_output_stem(task_jeans, display_category=label_jeans) == "Women Jeans 5%"


def test_resolve_output_paths_duplicate_policies(tmp_path):
    ex_dir = tmp_path / "Excel"
    pdf_dir = tmp_path / "PDF"
    ex_dir.mkdir()
    pdf_dir.mkdir()

    # Initial creation
    p_ex, p_pdf = resolve_output_paths(ex_dir, pdf_dir, "Women's 5%", policy="prompt")
    assert p_ex.name == "Women's 5%.xlsx"
    assert p_pdf.name == "Women's 5%.pdf"
    p_ex.write_text("x")
    p_pdf.write_text("x")

    # Prompt chooses number
    n_ex, n_pdf = resolve_output_paths(
        ex_dir, pdf_dir, "Women's 5%", policy="prompt", prompt_fn=lambda _: "n"
    )
    assert n_ex.name == "Women's 5% (2).xlsx"
    assert n_pdf.name == "Women's 5% (2).pdf"

    # Prompt chooses replace
    r_ex, r_pdf = resolve_output_paths(
        ex_dir, pdf_dir, "Women's 5%", policy="prompt", prompt_fn=lambda _: "r"
    )
    assert r_ex.name == "Women's 5%.xlsx"
    assert r_pdf.name == "Women's 5%.pdf"

    # Explicit replace policy
    r2_ex, r2_pdf = resolve_output_paths(ex_dir, pdf_dir, "Women's 5%", policy="replace")
    assert r2_ex.name == "Women's 5%.xlsx"
    assert r2_pdf.name == "Women's 5%.pdf"
