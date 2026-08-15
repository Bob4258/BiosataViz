from pathlib import Path

from biostatviz.io import load_table


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_two_group_gfp_example_loads_without_transformation():
    loaded = load_table(PROJECT_ROOT / "examples" / "data" / "two_group_gfp.csv")

    assert loaded.data.columns.tolist() == ["sample", "group", "gfp"]
    assert loaded.data.shape == (6, 3)
    assert loaded.data["sample"].tolist() == [
        "WT1",
        "WT2",
        "WT3",
        "KO1",
        "KO2",
        "KO3",
    ]
    assert loaded.data["group"].tolist() == ["WT", "WT", "WT", "KO", "KO", "KO"]
    assert loaded.data["gfp"].tolist() == [101, 98, 105, 142, 149, 145]
