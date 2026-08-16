from pathlib import Path

from biostatviz.inspection import InspectionIssue, InspectionReport, InspectionSeverity


def test_action_required_sets_requires_user_input():
    report = InspectionReport(
        source_path=Path("data.csv"),
        source_format="csv",
        issues=(InspectionIssue(code="POSSIBLE_HEADER_OFFSET", severity=InspectionSeverity.ACTION_REQUIRED, message="A later row may be the header.", candidates=("row:2",)),),
    )
    assert report.requires_user_input is True
    assert report.has_warnings is False


def test_warning_sets_has_warnings_without_requiring_input():
    report = InspectionReport(
        source_path=Path("data.csv"),
        source_format="csv",
        issues=(InspectionIssue(code="MIXED_NUMERIC_TEXT", severity=InspectionSeverity.WARNING, message="Mixed values detected."),),
    )
    assert report.requires_user_input is False
    assert report.has_warnings is True
