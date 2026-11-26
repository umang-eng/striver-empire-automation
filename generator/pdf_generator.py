"""Generate single-page green-header table-only PDF reports using ReportLab."""

from decimal import Decimal
import logging
from pathlib import Path
from typing import Any, Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

from core.exceptions import FileGenerationError
from core.models import ExtractionSummary, ProductRecord
from generator import COLUMNS

_ARIAL_REGULAR = "/System/Library/Fonts/Supplemental/Arial.ttf"
_ARIAL_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def _resolve_fonts() -> tuple[str, str]:
    """Register Arial TTF fonts on macOS when available; fallback to Helvetica."""
    registered = set(pdfmetrics.getRegisteredFontNames())
    if Path(_ARIAL_REGULAR).exists() and Path(_ARIAL_BOLD).exists():
        if "Arial" not in registered:
            pdfmetrics.registerFont(TTFont("Arial", _ARIAL_REGULAR))
        if "Arial-Bold" not in registered:
            pdfmetrics.registerFont(TTFont("Arial-Bold", _ARIAL_BOLD))
        return "Arial", "Arial-Bold"
    return "Helvetica", "Helvetica-Bold"


def _fmt_price(amount: Decimal, prefix: str = "") -> str:
    """Format price with exactly two decimal places and no commas or currency symbols."""
    del prefix
    return f"{amount:.2f}"


def _compute_dynamic_col_widths(
    records: list[ProductRecord],
    avail_width: float,
    currency_prefix: str,
) -> list[float]:
    """Compute column widths proportionally to content while staying within printable width."""
    max_sr = max([len(COLUMNS[0])] + [len(str(r.sr_no)) for r in records])
    max_name = max([len(COLUMNS[1])] + [len(r.name) for r in records])
    max_tp = max([len(COLUMNS[2])] + [len(_fmt_price(r.total_price, currency_prefix)) for r in records])
    max_lp = max([len(COLUMNS[3])] + [len(r.less_price_display) for r in records])
    max_rp = max([len(COLUMNS[4])] + [len(_fmt_price(r.real_price, currency_prefix)) for r in records])
    max_size = max([len(COLUMNS[5])] + [len(r.size) for r in records])
    max_type = max([len(COLUMNS[6])] + [len(r.category_type) for r in records])

    # Cap extreme single-cell text widths so other columns remain legible
    weights = [
        max(max_sr + 2, 7),
        min(max(max_name + 4, 22), 52),
        max(max_tp + 3, 12),
        max(max_lp + 3, 10),
        max(max_rp + 3, 12),
        min(max(max_size + 3, 9), 22),
        min(max(max_type + 4, 15), 26),
    ]
    total_weight = sum(weights)

    # For small tables, keep a comfortable spreadsheet-like width (not excessively stretched)
    target_width = min(avail_width, max(avail_width * 0.78, total_weight * 6.2))
    return [target_width * (w / total_weight) for w in weights]


def _build_table(
    records: list[ProductRecord],
    col_widths: list[float],
    font_size: float,
    h_pad: float,
    v_pad: float,
    header_color: colors.Color,
    currency_prefix: str,
    regular_font: str,
    bold_font: str,
) -> Table:
    """Build a ReportLab Table containing ONLY the 7 required columns and product records."""
    leading = max(font_size * 1.15, font_size + 0.8)

    header_style = ParagraphStyle(
        "TableHeader",
        fontName=bold_font,
        fontSize=font_size,
        leading=leading,
        textColor=colors.black,
        alignment=1,
    )
    cell_left = ParagraphStyle(
        "CellLeft",
        fontName=regular_font,
        fontSize=font_size,
        leading=leading,
        textColor=colors.black,
        alignment=0,
    )
    cell_center = ParagraphStyle(
        "CellCenter",
        parent=cell_left,
        alignment=1,
    )
    cell_right = ParagraphStyle(
        "CellRight",
        parent=cell_left,
        alignment=2,
    )

    rows: list[list[Any]] = [[Paragraph(escape(col), header_style) for col in COLUMNS]]

    for rec in records:
        rows.append(
            [
                Paragraph(str(rec.sr_no), cell_center),
                Paragraph(escape(rec.name), cell_left),
                Paragraph(escape(_fmt_price(rec.total_price, currency_prefix)), cell_right),
                Paragraph(escape(rec.less_price_display), cell_center),
                Paragraph(escape(_fmt_price(rec.real_price, currency_prefix)), cell_right),
                Paragraph(escape(rec.size), cell_center),
                Paragraph(escape(rec.category_type), cell_left),
            ]
        )

    table = Table(rows, colWidths=col_widths, hAlign="CENTER")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), header_color),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#333333")),
                ("BOX", (0, 0), (-1, -1), 1.0, colors.black),
                ("LINEBELOW", (0, 0), (-1, 0), 0.9, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), v_pad),
                ("BOTTOMPADDING", (0, 0), (-1, -1), v_pad),
                ("LEFTPADDING", (0, 0), (-1, -1), h_pad),
                ("RIGHTPADDING", (0, 0), (-1, -1), h_pad),
            ]
        )
    )
    return table


def generate_pdf_report(
    summary: ExtractionSummary,
    output_path: str | Path,
    settings: dict[str, Any],
    logger: Optional[logging.Logger] = None,
) -> Path:
    """Write ONLY the 7-column green-header product table onto strictly ONE landscape PDF page."""
    try:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        out_cfg = settings.get("output", {})
        currency_prefix = str(out_cfg.get("pdf_currency_prefix", ""))
        header_hex = str(out_cfg.get("header_bg_color", "#18B500"))
        header_color = colors.HexColor(header_hex)
        max_font = float(out_cfg.get("pdf_max_font_size", 9.5))
        min_readable_font = float(out_cfg.get("pdf_min_readable_font_size", 5.5))

        regular_font, bold_font = _resolve_fonts()

        page_w, page_h = landscape(A4)
        margin_x = 8 * mm
        margin_y = 8 * mm
        avail_w = page_w - 2 * margin_x
        avail_h = page_h - 2 * margin_y

        col_widths = _compute_dynamic_col_widths(summary.records, avail_w, currency_prefix)

        pdf_canvas = canvas.Canvas(str(target), pagesize=landscape(A4))

        chosen_table: Optional[Table] = None
        chosen_size = (0.0, 0.0)
        chosen_font = max_font

        # Step down font size and padding to fit cleanly within 1 page
        font_candidates = []
        f = max_font
        while f >= min_readable_font - 1e-6:
            font_candidates.append(round(f, 2))
            f -= 0.5

        for font_size in font_candidates:
            v_pad = max(1.2, round(font_size * 0.45, 2))
            h_pad = max(2.0, round(font_size * 0.52, 2))
            candidate_table = _build_table(
                records=summary.records,
                col_widths=col_widths,
                font_size=font_size,
                h_pad=h_pad,
                v_pad=v_pad,
                header_color=header_color,
                currency_prefix=currency_prefix,
                regular_font=regular_font,
                bold_font=bold_font,
            )
            tw, th = candidate_table.wrapOn(pdf_canvas, avail_w, 100000)
            chosen_table = candidate_table
            chosen_size = (tw, th)
            chosen_font = font_size
            if th <= avail_h and tw <= avail_w:
                break

        assert chosen_table is not None
        tw, th = chosen_size
        scale = 1.0

        # If dataset is too large even at minimum readable font size, warn and fit via uniform scaling
        if th > avail_h or tw > avail_w:
            # Expand col_widths to full avail_w first to reduce line wrapping before scaling
            full_col_widths = [w * (avail_w / sum(col_widths)) for w in col_widths]
            expanded_table = _build_table(
                records=summary.records,
                col_widths=full_col_widths,
                font_size=min_readable_font,
                h_pad=2.0,
                v_pad=1.0,
                header_color=header_color,
                currency_prefix=currency_prefix,
                regular_font=regular_font,
                bold_font=bold_font,
            )
            ew, eh = expanded_table.wrapOn(pdf_canvas, avail_w, 100000)
            chosen_table = expanded_table
            tw, th = ew, eh
            scale = min(avail_w / tw, avail_h / th, 1.0)
            warn_msg = (
                f"Dataset of {len(summary.records)} product(s) exceeds single-page landscape A4 height "
                f"at minimum readable font size ({min_readable_font}pt); applied {scale:.2f}x scaling "
                "to keep all records on 1 page without omitting any rows."
            )
            summary.warnings.append(warn_msg)
            if logger:
                logger.warning(warn_msg)

        draw_w = tw * scale
        draw_h = th * scale
        origin_x = (page_w - draw_w) / 2.0
        # Top-align near upper margin when tall, or vertically centered when compact
        origin_y = max(margin_y, page_h - margin_y - draw_h)

        pdf_canvas.saveState()
        pdf_canvas.translate(origin_x, origin_y)
        if scale < 1.0:
            pdf_canvas.scale(scale, scale)
        chosen_table.drawOn(pdf_canvas, 0, 0)
        pdf_canvas.restoreState()

        pdf_canvas.showPage()
        pdf_canvas.save()
        return target
    except Exception as exc:
        raise FileGenerationError(f"Failed to generate PDF file {output_path}: {exc}") from exc
