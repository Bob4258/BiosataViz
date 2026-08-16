from biostatviz.inspection import InspectionSeverity
from biostatviz.inspection.preview import TablePreview
from biostatviz.io import LoadingOptions


def test_metadata_prefix_produces_header_action_required():
    from biostatviz.inspection.checks import inspect_structure
    preview = TablePreview(rows=(("Experiment: screen", "", ""),("Date: 2026-08-16", "", ""),("sample", "group", "value"),("S1", "A", "10"),("S2", "B", "20")), delimiter=",", delimiter_candidates=(",",))
    result = inspect_structure(preview, base_options=LoadingOptions(delimiter=","))
    issue = next(i for i in result.issues if i.code == "POSSIBLE_HEADER_OFFSET")
    assert issue.severity is InspectionSeverity.ACTION_REQUIRED
    assert issue.candidates == ("row:2",)
    assert result.candidate_loading_options[0].header == 2


def test_duplicate_raw_column_labels_are_action_required():
    from biostatviz.inspection.checks import inspect_structure
    preview = TablePreview(rows=(("sample", "value", "value"), ("S1", "1", "2"), ("S2", "3", "4")), delimiter=",", delimiter_candidates=(",",))
    result = inspect_structure(preview, base_options=LoadingOptions(delimiter=","))
    issue = next(i for i in result.issues if i.code == "DUPLICATE_COLUMN_NAMES")
    assert issue.severity is InspectionSeverity.ACTION_REQUIRED
    assert issue.observed == ("value",)


def test_internal_blank_row_and_column_are_reported():
    from biostatviz.inspection.checks import inspect_structure
    preview = TablePreview(rows=(("sample", "", "value"),("S1", "", "1"),("", "", ""),("S2", "", "2")), delimiter=",", delimiter_candidates=(",",))
    result = inspect_structure(preview, base_options=LoadingOptions(delimiter=","))
    assert any(i.code == "BLANK_ROW" for i in result.issues)
    assert any(i.code == "BLANK_COLUMN" and "1" in i.observed for i in result.issues)
