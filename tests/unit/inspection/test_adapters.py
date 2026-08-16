from pathlib import Path

from biostatviz.inspection import InspectionIssue, InspectionReport, InspectionSeverity, TableRegion


def test_agent_questions_render_region_candidates_without_choosing():
    from biostatviz.inspection.agent import build_agent_questions
    regions = (TableRegion("region:1", "Data", 1, 3, 1, 2, 6, ("a", "b")), TableRegion("region:2", "Data", 1, 3, 4, 5, 6, ("x", "y")))
    report = InspectionReport(source_path=Path("book.xlsx"), source_format="xlsx", issues=(InspectionIssue(code="MULTIPLE_TABLE_REGIONS", severity=InspectionSeverity.ACTION_REQUIRED, message="Multiple regions.", candidates=("region:1", "region:2")),), regions=regions)
    questions = build_agent_questions(report)
    assert len(questions) == 1
    assert "A1:B3" in questions[0] and "D1:E3" in questions[0]


def test_cli_report_lists_severity_and_region_coordinates():
    from biostatviz.inspection.cli import format_cli_report
    region = TableRegion("region:1", "Data", 1, 3, 1, 2, 6, ("a", "b"))
    report = InspectionReport(source_path=Path("book.xlsx"), source_format="xlsx", issues=(InspectionIssue(code="MULTIPLE_TABLE_REGIONS", severity=InspectionSeverity.ACTION_REQUIRED, message="Multiple regions.", candidates=("region:1",)),), regions=(region,))
    text = format_cli_report(report)
    assert "[ACTION REQUIRED]" in text and "region:1" in text and "A1:B3" in text


def test_cli_region_resolver_returns_existing_region():
    from biostatviz.inspection.cli import resolve_cli_region
    regions = (TableRegion("region:1", "Data", 1, 3, 1, 2, 6), TableRegion("region:2", "Data", 1, 3, 4, 5, 6))
    report = InspectionReport(source_path=Path("book.xlsx"), source_format="xlsx", issues=(InspectionIssue(code="MULTIPLE_TABLE_REGIONS", severity=InspectionSeverity.ACTION_REQUIRED, message="Multiple regions.", candidates=("region:1", "region:2")),), regions=regions)
    assert resolve_cli_region(report, input_fn=lambda _: "2") is regions[1]


def _workbook_report_for_adapter_tests():
    from biostatviz.inspection import WorkbookInspectionReport, WorkbookSheetResult
    first = InspectionReport(source_path=Path("book.xlsx"), source_format="xlsx", inspected_sheet="A", regions=(TableRegion("region:1", "A", 1, 3, 1, 2, 6),))
    second = InspectionReport(source_path=Path("book.xlsx"), source_format="xlsx", inspected_sheet="B", issues=(InspectionIssue(code="MERGED_HEADER_DETECTED", severity=InspectionSeverity.ACTION_REQUIRED, message="Merged header.", observed=("B1:C1=Group",)),), regions=(TableRegion("region:1", "B", 1, 3, 1, 3, 8),))
    third = InspectionReport(source_path=Path("book.xlsx"), source_format="xlsx", inspected_sheet="C", issues=(InspectionIssue(code="BLANK_VALUES_PRESENT", severity=InspectionSeverity.INFO, message="One blank."),))
    return WorkbookInspectionReport(source_path=Path("book.xlsx"), sheets=(WorkbookSheetResult("A", first), WorkbookSheetResult("B", second), WorkbookSheetResult("C", third)))


def test_workbook_agent_summary_lists_all_sheets_and_counts():
    from biostatviz.inspection.agent import build_workbook_agent_summary
    text = build_workbook_agent_summary(_workbook_report_for_adapter_tests())
    assert "3 sheets inspected" in text
    assert "A" in text and "B" in text and "C" in text
    assert "Merged headers" in text
    assert "Choose one sheet, multiple sheets, or continue with all" in text


def test_workbook_cli_summary_uses_same_report_contract():
    from biostatviz.inspection.cli import format_workbook_summary
    text = format_workbook_summary(_workbook_report_for_adapter_tests())
    assert "Sheet" in text and "A" in text and "B" in text and "C" in text and "ACTION_REQUIRED" in text


def test_cli_sheet_selection_supports_all_single_and_multiple():
    from biostatviz.inspection.cli import resolve_cli_sheet_selection
    report = _workbook_report_for_adapter_tests()
    assert resolve_cli_sheet_selection(report, input_fn=lambda _: "all") == ("A", "B", "C")
    assert resolve_cli_sheet_selection(report, input_fn=lambda _: "2") == ("B",)
    assert resolve_cli_sheet_selection(report, input_fn=lambda _: "1,3") == ("A", "C")


def test_cli_sheet_selection_rejects_duplicate_or_out_of_range_choices():
    import pytest
    from biostatviz.inspection.cli import resolve_cli_sheet_selection
    report = _workbook_report_for_adapter_tests()
    with pytest.raises(ValueError, match="Duplicate"): resolve_cli_sheet_selection(report, input_fn=lambda _: "1,1")
    with pytest.raises(ValueError, match="out of range"): resolve_cli_sheet_selection(report, input_fn=lambda _: "4")
