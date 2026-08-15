from pathlib import Path

import pandas as pd
from biostatviz.io import load_table


def test_load_csv_preserves_values_columns_and_missing_data(tmp_path: Path):
    csv_path = tmp_path / "experiment.csv"
    csv_path.write_text(
        "sample,group,gfp,note\n"
        "WT1,WT,101,ok\n"
        "WT2,WT,,missing\n"
        "KO1,KO,145,ok\n",
        encoding="utf-8",
    )

    loaded = load_table(csv_path)

    expected = pd.read_csv(csv_path)
    pd.testing.assert_frame_equal(loaded.data, expected)
    assert loaded.source_path == csv_path.resolve()
    assert loaded.source_format == "csv"
    assert loaded.sheet_name is None
