from pathlib import Path

import pandas as pd
import pytest

from biostatviz.io import (
    LoadedTable,
    TableNotFoundError,
    TableReadError,
    UnsupportedTableFormatError,
    load_table,
)


def test_loaded_table_preserves_dataframe_and_source_metadata():
    df = pd.DataFrame({"group": ["WT", "KO"], "gfp": [100, 140]})
    loaded = LoadedTable(
        data=df,
        source_path=Path("example.csv"),
        source_format="csv",
        sheet_name=None,
    )
    assert loaded.data is df
    assert loaded.source_path == Path("example.csv")
    assert loaded.source_format == "csv"
    assert loaded.sheet_name is None


def test_load_table_rejects_missing_file(tmp_path: Path):
    missing = tmp_path / "missing.csv"
    with pytest.raises(TableNotFoundError, match="does not exist"):
        load_table(missing)


def test_load_table_rejects_unsupported_extension(tmp_path: Path):
    txt_path = tmp_path / "data.txt"
    txt_path.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(UnsupportedTableFormatError, match="Unsupported table format"):
        load_table(txt_path)


def test_csv_rejects_excel_sheet_argument(tmp_path: Path):
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(TableReadError, match="sheet_name is only valid"):
        load_table(csv_path, sheet_name="Sheet1")


from biostatviz.io import ExcelSheetNotFoundError


def test_xlsx_rejects_missing_sheet(tmp_path: Path):
    xlsx_path = tmp_path / "experiment.xlsx"
    pd.DataFrame({"a": [1]}).to_excel(
        xlsx_path,
        sheet_name="Data",
        index=False,
        engine="openpyxl",
    )

    with pytest.raises(ExcelSheetNotFoundError, match="Excel sheet not found"):
        load_table(xlsx_path, sheet_name="Missing")


def test_xlsx_wraps_corrupt_file_as_table_read_error(tmp_path: Path):
    xlsx_path = tmp_path / "broken.xlsx"
    xlsx_path.write_bytes(b"this is not an xlsx archive")
    with pytest.raises(TableReadError, match="Failed to read XLSX"):
        load_table(xlsx_path)
