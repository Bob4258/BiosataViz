from pathlib import Path

from biostatviz.io import load_table


def test_csv_preserves_user_authored_na_like_tokens_by_default(tmp_path: Path):
    path = tmp_path / "tokens.csv"
    path.write_text(
        "sample,value\n"
        "S1,10\n"
        "S2,NA\n"
        "S3,N/A\n"
        "S4,-\n",
        encoding="utf-8",
    )

    loaded = load_table(path)

    assert loaded.data["value"].tolist() == ["10", "NA", "N/A", "-"]

import pandas as pd
import pytest

from biostatviz.io import LoadingOptions, TableReadError


def test_csv_applies_explicit_delimiter_and_header(tmp_path: Path):
    path = tmp_path / "semicolon.csv"
    path.write_text(
        "experiment note\n"
        "sample;value\n"
        "S1;10\n"
        "S2;20\n",
        encoding="utf-8",
    )

    loaded = load_table(path, options=LoadingOptions(delimiter=";", header=1))

    assert loaded.data.columns.tolist() == ["sample", "value"]
    assert loaded.data["sample"].tolist() == ["S1", "S2"]


def test_load_table_rejects_duplicate_sheet_configuration(tmp_path: Path):
    path = tmp_path / "book.xlsx"
    pd.DataFrame({"x": [1]}).to_excel(path, index=False, engine="openpyxl")

    with pytest.raises(TableReadError, match="either with sheet_name or LoadingOptions"):
        load_table(path, sheet_name="Sheet1", options=LoadingOptions(sheet_name="Sheet1"))
