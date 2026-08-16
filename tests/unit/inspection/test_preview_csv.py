from pathlib import Path

import pytest

from biostatviz.inspection import InspectionReadError
from biostatviz.inspection.preview import read_csv_preview


def test_csv_preview_preserves_raw_na_tokens(tmp_path: Path):
    path = tmp_path / "raw.csv"
    path.write_text("sample,value\nS1,NA\nS2,N/A\n", encoding="utf-8")
    preview = read_csv_preview(path, encoding="utf-8-sig", delimiter=",", max_rows=10)
    assert preview.rows[1] == ("S1", "NA")
    assert preview.rows[2] == ("S2", "N/A")


def test_csv_preview_detects_semicolon_delimiter(tmp_path: Path):
    path = tmp_path / "data.csv"
    path.write_text("sample;value\nS1;1\nS2;2\n", encoding="utf-8")
    preview = read_csv_preview(path, max_rows=10)
    assert preview.delimiter == ";"
    assert preview.delimiter_candidates == (";",)


def test_csv_preview_preserves_tied_delimiter_candidates(tmp_path: Path):
    path = tmp_path / "ambiguous.csv"
    path.write_text("a,b;c\nd,e;f\n", encoding="utf-8")
    preview = read_csv_preview(path, max_rows=10)
    assert preview.delimiter is None
    assert preview.delimiter_candidates == (",", ";")


def test_csv_preview_wraps_decode_failure(tmp_path: Path):
    path = tmp_path / "bad.csv"
    path.write_bytes(b"\xff\xfe\xff")
    with pytest.raises(InspectionReadError, match="bad.csv"):
        read_csv_preview(path, encoding="utf-8")
