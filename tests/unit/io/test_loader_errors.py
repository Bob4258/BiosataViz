from pathlib import Path

import pandas as pd

from biostatviz.io import LoadedTable


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
