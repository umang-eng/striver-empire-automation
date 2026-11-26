"""Generate clean green-header Excel product tables using OpenPyXL."""

from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from core.exceptions import FileGenerationError
from core.models import ExtractionSummary
from generator import COLUMNS

_ZEBRA_FILL = PatternFill(start_color="F5F5F5", end_color="F5F5F5", fill_type="solid")
_WHITE_FILL = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

_GRID_SIDE = Side(border_style="thin", color="333333")
_OUTER_SIDE = Side(border_style="medium", color="000000")


def _cell_border(row: int, col: int, max_row: int, max_col: int) -> Border:
    """Apply inner dark-grey grid lines and solid black outer border."""
    return Border(
        left=_OUTER_SIDE if col == 1 else _GRID_SIDE,
        right=_OUTER_SIDE if col == max_col else _GRID_SIDE,
        top=_OUTER_SIDE if row == 1 else _GRID_SIDE,
        bottom=_OUTER_SIDE if row == max_row else _GRID_SIDE,
    )


def _auto_adjust_column_widths(ws, max_width: int = 48, min_width: int = 10) -> None:
    """Compute column widths from cell contents with sensible bounds."""
    for col_idx in range(1, ws.max_column + 1):
        col_letter = get_column_letter(col_idx)
        longest = min_width
        for row in ws.iter_rows(min_col=col_idx, max_col=col_idx, values_only=True):
            val = row[0]
            if val is None:
                continue
            for line in str(val).splitlines() or [str(val)]:
                longest = max(longest, len(line) + 3)
        ws.column_dimensions[col_letter].width = min(max(longest, min_width), max_width)


def generate_excel_report(
    summary: ExtractionSummary,
    output_path: str | Path,
    settings: dict[str, Any],
) -> Path:
    """Write ONLY the 7-column product table to Excel matching the green-header layout."""
    try:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        out_cfg = settings.get("output", {})
        currency_fmt = out_cfg.get("excel_currency_format", "0.00")
        header_hex = str(out_cfg.get("header_bg_color", "#18B500")).lstrip("#")
        header_fill = PatternFill(start_color=header_hex, end_color=header_hex, fill_type="solid")

        wb = Workbook()
        ws = wb.active
        ws.title = "Products"

        # Header row (Row 1) — bright green background, black bold Arial text
        ws.append(COLUMNS)
        ws.row_dimensions[1].height = 26
        header_font = Font(name="Arial", size=11, bold=True, color="000000")
        data_font = Font(name="Arial", size=10, color="000000")

        max_row = max(1, len(summary.records) + 1)
        max_col = len(COLUMNS)

        for col_idx in range(1, max_col + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = _cell_border(1, col_idx, max_row, max_col)

        ws.freeze_panes = "A2"

        for idx, rec in enumerate(summary.records, start=2):
            ws.append(
                [
                    rec.sr_no,
                    rec.name,
                    rec.total_price,
                    rec.less_price_display,
                    rec.real_price,
                    rec.size,
                    rec.category_type,
                ]
            )
            ws.row_dimensions[idx].height = 20
            row_fill = _ZEBRA_FILL if (idx % 2) == 1 else _WHITE_FILL

            for col_idx in range(1, max_col + 1):
                cell = ws.cell(row=idx, column=col_idx)
                cell.font = data_font
                cell.fill = row_fill
                cell.border = _cell_border(idx, col_idx, max_row, max_col)

                if col_idx in (1, 4, 6):
                    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                elif col_idx in (3, 5):
                    cell.number_format = currency_fmt
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

        ws.auto_filter.ref = f"A1:G{max_row}"

        _auto_adjust_column_widths(ws)
        ws.column_dimensions["A"].width = max(ws.column_dimensions["A"].width or 9, 9)
        ws.column_dimensions["B"].width = max(ws.column_dimensions["B"].width or 28, 30)
        ws.column_dimensions["C"].width = max(ws.column_dimensions["C"].width or 13, 14)
        ws.column_dimensions["D"].width = max(ws.column_dimensions["D"].width or 12, 12)
        ws.column_dimensions["E"].width = max(ws.column_dimensions["E"].width or 13, 14)
        ws.column_dimensions["F"].width = max(ws.column_dimensions["F"].width or 12, 12)
        ws.column_dimensions["G"].width = max(ws.column_dimensions["G"].width or 18, 20)

        wb.save(target)
        return target
    except Exception as exc:
        raise FileGenerationError(f"Failed to generate Excel file {output_path}: {exc}") from exc
