from pathlib import Path

import pandas as pd
from biostatviz.io import load_table


def test_load_xlsx_uses_first_sheet_by_default(tmp_path: Path):
    xlsx_path = tmp_path / "experiment.xlsx"
    first = pd.DataFrame({"sample": ["WT1", "KO1"], "gfp": [101, 145]})
    second = pd.DataFrame({"ignore": [1, 2]})

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        first.to_excel(writer, sheet_name="Experiment", index=False)
        second.to_excel(writer, sheet_name="Other", index=False)

    loaded = load_table(xlsx_path)

    pd.testing.assert_frame_equal(loaded.data, first)
    assert loaded.source_format == "xlsx"
    assert loaded.sheet_name == 0


def test_load_xlsx_named_sheet(tmp_path: Path):
    xlsx_path = tmp_path / "experiment.xlsx"
    expected = pd.DataFrame({"group": ["WT", "KO"], "gfp": [100, 140]})

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        pd.DataFrame({"metadata": ["x"]}).to_excel(
            writer, sheet_name="Metadata", index=False
        )
        expected.to_excel(writer, sheet_name="Data", index=False)

    loaded = load_table(xlsx_path, sheet_name="Data")

    pd.testing.assert_frame_equal(loaded.data, expected)
    assert loaded.sheet_name == "Data"
