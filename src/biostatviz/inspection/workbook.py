"""Workbook-level batch inspection over independent XLSX worksheets."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import openpyxl

from biostatviz.io import (
    ExcelSheetNotFoundError,
    TableNotFoundError,
    UnsupportedTableFormatError,
)

from .errors import InspectionReadError
from .inspector import inspect_table
from .models import WorkbookInspectionReport, WorkbookSheetResult


def _workbook_sheet_names(path: Path) -> tuple[str, ...]:
    try:
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=False)
    except Exception as exc:
        raise InspectionReadError(f"Failed to preview XLSX file: {path}") from exc
    try:
        return tuple(workbook.sheetnames)
    finally:
        workbook.close()


def _resolve_selectors(
    names: tuple[str, ...],
    selectors: Sequence[str | int] | None,
) -> tuple[str, ...]:
    if selectors is None:
        return names

    resolved: list[str] = []
    seen: set[str] = set()
    for selector in selectors:
        if isinstance(selector, bool):
            raise ExcelSheetNotFoundError(f"Excel sheet not found: {selector!r}")
        if isinstance(selector, int):
            if selector < 0 or selector >= len(names):
                raise ExcelSheetNotFoundError(f"Excel sheet not found: {selector!r}")
            name = names[selector]
        else:
            name = selector
            if name not in names:
                raise ExcelSheetNotFoundError(f"Excel sheet not found: {selector!r}")
        if name in seen:
            raise ValueError(f"Duplicate sheet selector resolves to worksheet {name!r}.")
        seen.add(name)
        resolved.append(name)
    return tuple(resolved)


def inspect_workbook(
    path: str | Path,
    *,
    sheets: Sequence[str | int] | None = None,
    max_rows: int = 50,
    max_columns: int = 50,
) -> WorkbookInspectionReport:
    """Inspect all selected XLSX sheets independently, defaulting to all sheets."""
    source_path = Path(path).expanduser().resolve()
    if not source_path.exists():
        raise TableNotFoundError(f"Table file does not exist: {source_path}")
    if source_path.suffix.lower() != ".xlsx":
        raise UnsupportedTableFormatError(
            f"Unsupported workbook format '{source_path.suffix.lower() or '<none>'}'. "
            "inspect_workbook supports .xlsx only."
        )

    names = _workbook_sheet_names(source_path)
    selected_names = _resolve_selectors(names, sheets)
    results: list[WorkbookSheetResult] = []
    for name in selected_names:
        report = inspect_table(
            source_path,
            sheet_name=name,
            max_rows=max_rows,
            max_columns=max_columns,
        )
        results.append(WorkbookSheetResult(sheet_name=name, report=report))

    return WorkbookInspectionReport(source_path=source_path, sheets=tuple(results))
