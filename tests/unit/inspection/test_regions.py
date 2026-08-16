from biostatviz.inspection.preview import MergedRange, TablePreview


def test_side_by_side_tables_remain_separate_regions():
    from biostatviz.inspection.regions import discover_regions
    preview = TablePreview(rows=(("a", "b", "", "x", "y"),(1, 2, "", 3, 4),(5, 6, "", 7, 8)), sheet_name="Sheet1", apparent_rows=3, apparent_columns=5)
    regions, truncated = discover_regions(preview)
    assert truncated is False
    assert [r.a1_range for r in regions] == ["A1:B3", "D1:E3"]
    assert [r.region_id for r in regions] == ["region:1", "region:2"]


def test_vertically_aligned_fragments_with_one_blank_row_merge():
    from biostatviz.inspection.regions import discover_regions
    preview = TablePreview(rows=(("a", "b"),(1, 2),("", ""),(3, 4),(5, 6)), sheet_name="Sheet1", apparent_rows=5, apparent_columns=2)
    regions, _ = discover_regions(preview)
    assert [r.a1_range for r in regions] == ["A1:B5"]


def test_fragments_with_two_blank_rows_remain_separate():
    from biostatviz.inspection.regions import discover_regions
    preview = TablePreview(rows=(("a", "b"),(1, 2),("", ""),("", ""),(3, 4),(5, 6)), sheet_name="Sheet1", apparent_rows=6, apparent_columns=2)
    regions, _ = discover_regions(preview)
    assert [r.a1_range for r in regions] == ["A1:B2", "A5:B6"]


def test_merged_range_extends_occupancy_width():
    from biostatviz.inspection.regions import discover_regions
    preview = TablePreview(rows=(("Group", None, None), (1, 2, 3), (4, 5, 6)), sheet_name="Sheet1", merged_ranges=(MergedRange(1, 1, 1, 3, "Group"),), apparent_rows=3, apparent_columns=3)
    regions, _ = discover_regions(preview)
    assert [r.a1_range for r in regions] == ["A1:C3"]
