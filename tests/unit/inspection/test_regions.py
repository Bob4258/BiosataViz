from biostatviz.inspection.preview import MergedRange, TablePreview


def test_one_blank_spacer_column_stays_inside_one_region():
    from biostatviz.inspection.regions import discover_regions

    preview = TablePreview(
        rows=(
            ("a", "b", "", "x", "y"),
            (1, 2, "", 3, 4),
            (5, 6, "", 7, 8),
        ),
        sheet_name="Sheet1",
        apparent_rows=3,
        apparent_columns=5,
    )
    regions, truncated = discover_regions(preview)
    assert truncated is False
    assert [r.a1_range for r in regions] == ["A1:E3"]
    assert [r.region_id for r in regions] == ["region:1"]


def test_one_blank_row_is_a_hard_region_boundary():
    from biostatviz.inspection.regions import discover_regions

    preview = TablePreview(
        rows=(
            ("a", "b"),
            (1, 2),
            ("", ""),
            (3, 4),
            (5, 6),
        ),
        sheet_name="Sheet1",
        apparent_rows=5,
        apparent_columns=2,
    )
    regions, _ = discover_regions(preview)
    assert [r.a1_range for r in regions] == ["A1:B2", "A4:B5"]


def test_fragments_with_two_blank_rows_remain_separate():
    from biostatviz.inspection.regions import discover_regions

    preview = TablePreview(
        rows=(
            ("a", "b"),
            (1, 2),
            ("", ""),
            ("", ""),
            (3, 4),
            (5, 6),
        ),
        sheet_name="Sheet1",
        apparent_rows=6,
        apparent_columns=2,
    )
    regions, _ = discover_regions(preview)
    assert [r.a1_range for r in regions] == ["A1:B2", "A5:B6"]


def test_merged_range_extends_occupancy_width():
    from biostatviz.inspection.regions import discover_regions

    preview = TablePreview(
        rows=(("Group", None, None), (1, 2, 3), (4, 5, 6)),
        sheet_name="Sheet1",
        merged_ranges=(MergedRange(1, 1, 1, 3, "Group"),),
        apparent_rows=3,
        apparent_columns=3,
    )
    regions, _ = discover_regions(preview)
    assert [r.a1_range for r in regions] == ["A1:C3"]


def test_two_blank_columns_split_side_by_side_regions():
    from biostatviz.inspection.regions import discover_regions

    preview = TablePreview(
        rows=(
            ("a", "b", "", "", "x", "y"),
            (1, 2, "", "", 3, 4),
            (5, 6, "", "", 7, 8),
        ),
        sheet_name="Sheet1",
        apparent_rows=3,
        apparent_columns=6,
    )
    regions, truncated = discover_regions(preview)
    assert truncated is False
    assert [r.a1_range for r in regions] == ["A1:B3", "E1:F3"]


def test_multiple_single_blank_spacers_remain_one_region():
    from biostatviz.inspection.regions import discover_regions

    preview = TablePreview(
        rows=(
            ("a", "b", "c", "d", "", "e", "f", "", "g", "h"),
            (1, 2, 3, 4, "", 5, 6, "", 7, 8),
            (9, 10, 11, 12, "", 13, 14, "", 15, 16),
        ),
        sheet_name="Sheet1",
        apparent_rows=3,
        apparent_columns=10,
    )
    regions, _ = discover_regions(preview)
    assert [r.a1_range for r in regions] == ["A1:J3"]
