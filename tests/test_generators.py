"""Unit tests for Excel and strictly single-page table-only PDF generation."""

from datetime import datetime
from decimal import Decimal
import re

from openpyxl import load_workbook

from core.logger import setup_logging
from core.models import ExtractionSummary, ParsedTask, ProductRecord
from generator import COLUMNS, pick_random_header_color, resolve_header_color
from generator.excel_generator import generate_excel_report
from generator.pdf_generator import generate_pdf_report


def _build_summary(count: int = 2) -> ExtractionSummary:
    task = ParsedTask(
        raw_message="women 25%",
        category="Women",
        discount_percent=Decimal("25"),
    )
    subcategories = ["Shirt's", "Formal Pant", "Tops", "Women Jeans", "Blazers"]
    records = [
        ProductRecord(
            sr_no=i,
            name=f"Women Sample Product {i}",
            total_price=Decimal("1699.00") if i == 1 else Decimal("999.00"),
            discount_percent=Decimal("25"),
            real_price=Decimal("1274.25") if i == 1 else Decimal("749.25"),
            size="M, L",
            category_type=subcategories[(i - 1) % len(subcategories)],
            url=f"https://striverempire.com/product/detail/sample-{i}",
        )
        for i in range(1, count + 1)
    ]
    return ExtractionSummary(
        task=task,
        category_url="https://striverempire.com/product/list/womens",
        started_at=datetime(2026, 11, 26, 18, 30, 1),
        completed_at=datetime(2026, 11, 26, 18, 30, 20),
        expected_total_from_site=count,
        discovered_count=count,
        records=records,
    )


def _count_pdf_pages(pdf_bytes: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page(?!s)\b", pdf_bytes))


def test_random_header_color_varies_and_is_readable():
    colors_picked = {pick_random_header_color() for _ in range(12)}
    assert len(colors_picked) > 1
    for c in colors_picked:
        assert re.fullmatch(r"#[0-9A-F]{6}", c)

    # Configured static fallback works when randomize_header_color is disabled
    static_color = resolve_header_color(
        {"output": {"randomize_header_color": False, "header_bg_color": "#18B500"}}
    )
    assert static_color == "#18B500"


def test_excel_and_pdf_table_only_randomized_header_no_currency_symbols(tmp_path):
    summary = _build_summary(count=3)
    settings = {
        "output": {
            "excel_currency_format": "0.00",
            "pdf_currency_prefix": "",
            "header_bg_color": "#18B500",
            "randomize_header_color": True,
            "pdf_max_font_size": 9.5,
            "pdf_min_readable_font_size": 5.5,
        }
    }

    xlsx_path1 = tmp_path / "Excel" / "Women_1.xlsx"
    xlsx_path2 = tmp_path / "Excel" / "Women_2.xlsx"
    pdf_path = tmp_path / "PDF" / "Women_1.pdf"

    generate_excel_report(summary, xlsx_path1, settings)
    generate_excel_report(summary, xlsx_path2, settings)
    generate_pdf_report(summary, pdf_path, settings)

    # Verify repeated generation produces randomized header fills
    observed_fills = set()
    for idx in range(5):
        p = tmp_path / "Excel" / f"rand_{idx}.xlsx"
        generate_excel_report(summary, p, settings)
        observed_fills.add(load_workbook(p)["Products"].cell(1, 1).fill.start_color.rgb)
    assert len(observed_fills) > 1

    wb = load_workbook(xlsx_path1)
    assert wb.sheetnames == ["Products"]
    ws = wb["Products"]
    assert ws.max_row == 4
    assert ws.max_column == 7
    headers = [ws.cell(row=1, column=i).value for i in range(1, 8)]
    assert headers == COLUMNS == [
        "Sr. no.",
        "Product Name",
        "Total Price",
        "Less Price",
        "Real Price",
        "Size",
        "Type",
    ]
    assert ws.cell(row=1, column=1).font.bold is True
    assert ws.freeze_panes == "A2"
    assert ws.auto_filter.ref == "A1:G4"

    assert ws.cell(row=2, column=1).value == 1
    assert Decimal(str(ws.cell(row=2, column=3).value)) == Decimal("1699")
    assert ws.cell(row=2, column=3).number_format == "0.00"
    assert ws.cell(row=2, column=4).value == "25%"
    assert Decimal(str(ws.cell(row=2, column=5).value)) == Decimal("1274.25")
    assert ws.cell(row=2, column=5).number_format == "0.00"
    assert ws.cell(row=2, column=6).value == "M, L"
    assert ws.cell(row=2, column=7).value == "Shirt's"

    pdf_bytes = pdf_path.read_bytes()
    assert pdf_bytes.startswith(b"%PDF")
    assert _count_pdf_pages(pdf_bytes) == 1
    assert not summary.warnings


def test_pdf_large_dataset_fits_single_page_with_warning(tmp_path):
    summary = _build_summary(count=140)
    logger = setup_logging(log_dir=tmp_path / "logs", level="WARNING")
    settings = {
        "output": {
            "pdf_currency_prefix": "",
            "header_bg_color": "#18B500",
            "randomize_header_color": True,
            "pdf_max_font_size": 9.5,
            "pdf_min_readable_font_size": 5.5,
        }
    }
    pdf_path = tmp_path / "PDF" / "large_single_page.pdf"
    generate_pdf_report(summary, pdf_path, settings, logger=logger)

    pdf_bytes = pdf_path.read_bytes()
    assert _count_pdf_pages(pdf_bytes) == 1
    assert any("140 product(s)" in w for w in summary.warnings)
