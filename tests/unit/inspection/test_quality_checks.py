from biostatviz.inspection.preview import TablePreview


def test_placeholder_token_inside_numeric_column_is_reported_verbatim():
    from biostatviz.inspection.checks import inspect_quality
    preview = TablePreview(rows=(("sample", "intensity"),("S1", "10.1"),("S2", "ND"),("S3", "12.5")), delimiter=",", delimiter_candidates=(",",))
    issues = inspect_quality(preview, header_row=0)
    issue = next(i for i in issues if i.code == "PLACEHOLDER_TOKEN_IN_NUMERIC_COLUMN")
    assert issue.location == "column:intensity"
    assert issue.observed == ("ND",)


def test_mixed_numeric_text_is_warning():
    from biostatviz.inspection.checks import inspect_quality
    preview = TablePreview(rows=(("sample", "value"), ("S1", "1"), ("S2", "oops"), ("S3", "2")), delimiter=",", delimiter_candidates=(",",))
    issues = inspect_quality(preview, header_row=0)
    issue = next(i for i in issues if i.code == "MIXED_NUMERIC_TEXT")
    assert issue.observed == ("oops",)


def test_blank_values_are_reported_without_imputation():
    from biostatviz.inspection.checks import inspect_quality
    preview = TablePreview(rows=(("sample", "value"), ("S1", "1"), ("S2", ""), ("S3", "2")), delimiter=",", delimiter_candidates=(",",))
    original = preview.rows
    issues = inspect_quality(preview, header_row=0)
    issue = next(i for i in issues if i.code == "BLANK_VALUES_PRESENT")
    assert issue.observed == ("count:1",)
    assert preview.rows == original


def test_duplicate_identifier_is_conservative():
    from biostatviz.inspection.checks import inspect_quality
    preview = TablePreview(rows=(("sample", "value"), ("S1", "1"), ("S1", "2")), delimiter=",", delimiter_candidates=(",",))
    assert any(i.code == "POSSIBLE_DUPLICATE_IDENTIFIER" for i in inspect_quality(preview, header_row=0))


def test_repeated_measurement_values_are_not_called_duplicate_identifiers():
    from biostatviz.inspection.checks import inspect_quality
    preview = TablePreview(rows=(("group", "value"), ("A", "1.0"), ("B", "1.0")), delimiter=",", delimiter_candidates=(",",))
    assert not any(i.code == "POSSIBLE_DUPLICATE_IDENTIFIER" for i in inspect_quality(preview, header_row=0))
