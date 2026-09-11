"""Writing the one file the client actually opens.

Two sheets: Summary (one row per store, with a status column) and Detail (the
line items). The status column is the reason the spreadsheet is trustworthy --
a store missing from the file is indistinguishable from a store that sold
nothing, so a failed source has to be visible *in the deliverable*, not only in
a log the client will never read.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

HEADER_FILL = PatternFill("solid", fgColor="1F3864")
HEADER_FONT = Font(color="FFFFFF", bold=True)
FAILED_FILL = PatternFill("solid", fgColor="F8CBAD")
FAILED_FONT = Font(color="9C0006", bold=True)
PARTIAL_FONT = Font(color="9C5700", bold=True)
OK_FONT = Font(color="1E6B33", bold=True)
TOTAL_FILL = PatternFill("solid", fgColor="D9E1F2")

MONEY_FORMAT = "#,##0.00"
MONEY_COLUMNS = {"Gross", "Commission", "Cost", "Net profit", "Unit price", "Margin %"}
# The failure reason is a sentence, not a value: wrap it at a fixed width so it
# stays readable and does not push the rest of the sheet off the printed page.
WRAPPED_COLUMNS = {"Note": 46}


def write_workbook(path: Path, summary: pd.DataFrame, detail: pd.DataFrame) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        detail.to_excel(writer, sheet_name="Detail", index=False)
        _style(writer.sheets["Summary"], summary, status_column="Status")
        _style(writer.sheets["Detail"], detail)
    return path


def _style(sheet: Worksheet, frame: pd.DataFrame, status_column: str | None = None) -> None:
    columns = list(frame.columns)

    for index, name in enumerate(columns, start=1):
        cell = sheet.cell(row=1, column=index)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        width = max(len(str(name)), *(len(str(v)) for v in frame[name].astype(str))) + 2
        sheet.column_dimensions[get_column_letter(index)].width = min(
            WRAPPED_COLUMNS.get(name, max(width, 10)), 52
        )
        for row in range(2, sheet.max_row + 1):
            cell = sheet.cell(row=row, column=index)
            if name in MONEY_COLUMNS:
                cell.number_format = MONEY_FORMAT
            if name in WRAPPED_COLUMNS:
                cell.alignment = Alignment(wrap_text=True, vertical="top")

    _fit_row_heights(sheet, frame)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions

    # The summary is something people print and hand around in a meeting, so
    # make it land on one landscape page instead of four ragged ones.
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.print_title_rows = "1:1"

    if status_column and status_column in columns:
        _highlight_status(sheet, frame, columns, status_column)


def _fit_row_heights(sheet: Worksheet, frame: pd.DataFrame) -> None:
    """Give rows with wrapped text enough height to show all of it.

    Neither Excel nor LibreOffice recomputes auto-height for a file written by
    a library, so a long failure reason would be silently clipped -- the one
    piece of text on the sheet that must not be.
    """
    for name, width in WRAPPED_COLUMNS.items():
        if name not in frame.columns:
            continue
        for offset, value in enumerate(frame[name].astype(str), start=2):
            text = "" if value in ("nan", "None") else value
            lines = max(1, -(-len(text) // (width - 4)))
            if lines > 1:
                sheet.row_dimensions[offset].height = 14 * lines


def _highlight_status(
    sheet: Worksheet, frame: pd.DataFrame, columns: list[str], status_column: str
) -> None:
    """Colour the status cell, and shade the whole row when a store failed."""
    status_index = columns.index(status_column) + 1
    status_fonts = {"FAILED": FAILED_FONT, "PARTIAL": PARTIAL_FONT, "OK": OK_FONT}

    for offset, status in enumerate(frame[status_column], start=2):
        is_total = frame.iloc[offset - 2]["Store ID"] == "TOTAL"

        if status == "FAILED":
            for column in range(1, len(columns) + 1):
                sheet.cell(row=offset, column=column).fill = FAILED_FILL
        if is_total:
            for column in range(1, len(columns) + 1):
                cell = sheet.cell(row=offset, column=column)
                cell.fill = TOTAL_FILL
                cell.font = Font(bold=True)

        status_cell = sheet.cell(row=offset, column=status_index)
        status_cell.alignment = Alignment(horizontal="center")
        status_cell.font = status_fonts.get(status, OK_FONT)
