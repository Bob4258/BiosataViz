"""Deterministic CSV/XLSX table loading."""

from pathlib import Path

import pandas as pd

from .errors import (
    ExcelSheetNotFoundError,
    TableNotFoundError,
    TableReadError,
    UnsupportedTableFormatError,
)
from .models import LoadedTable

SUPPORTED_SUFFIXES = {".csv", ".xlsx"}


def load_table(
    path: str | Path,
    sheet_name: str | int | None = None,
) -> LoadedTable:
    """Load a supported tabular file without silently transforming its contents."""

    source_path = Path(path).expanduser().resolve()

    if not source_path.exists():
        raise TableNotFoundError(f"Table file does not exist: {source_path}")

    suffix = source_path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise UnsupportedTableFormatError(
            f"Unsupported table format '{suffix or '<none>'}'. "
            "Supported formats are .csv and .xlsx."
        )

    if suffix == ".xlsx":
        requested_sheet = 0 if sheet_name is None else sheet_name
        try:
            data = pd.read_excel(
                source_path,
                sheet_name=requested_sheet,
                engine="openpyxl",
            )
        except ValueError as exc:
            message = str(exc)
            if "Worksheet" in message or "sheet" in message.lower():
                raise ExcelSheetNotFoundError(
                    f"Excel sheet not found: {requested_sheet!r} in {source_path}"
                ) from exc
            raise TableReadError(f"Failed to read XLSX file: {source_path}") from exc
        except Exception as exc:
            raise TableReadError(f"Failed to read XLSX file: {source_path}") from exc

        return LoadedTable(
            data=data,
            source_path=source_path,
            source_format="xlsx",
            sheet_name=requested_sheet,
        )

    if sheet_name is not None:
        raise TableReadError("sheet_name is only valid for .xlsx files.")

    try:
        data = pd.read_csv(source_path)
    except Exception as exc:
        raise TableReadError(f"Failed to read CSV file: {source_path}") from exc

    return LoadedTable(
        data=data,
        source_path=source_path,
        source_format="csv",
        sheet_name=None,
    )
