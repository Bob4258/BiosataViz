"""Agent-facing rendering of deterministic inspection reports."""

from __future__ import annotations

from .models import InspectionReport, InspectionSeverity


def _region_details(report: InspectionReport) -> str:
    return "; ".join(
        f"{region.region_id} {region.a1_range}"
        + (f" preview: {' | '.join(region.preview_values)}" if region.preview_values else "")
        for region in report.regions
    )


def build_agent_questions(report: InspectionReport) -> tuple[str, ...]:
    """Render questions only for unresolved ACTION_REQUIRED issues."""
    questions: list[str] = []
    for issue in report.issues:
        if issue.severity is not InspectionSeverity.ACTION_REQUIRED:
            continue
        if issue.code == "MULTIPLE_TABLE_REGIONS":
            details = _region_details(report)
            questions.append(f"Multiple table regions were detected. {details}. Which region should be inspected?")
        elif issue.code == "MULTIPLE_PLAUSIBLE_SHEETS":
            questions.append(
                "Multiple worksheets contain plausible tables. Choose one explicitly: "
                + ", ".join(issue.candidates)
            )
        elif issue.code in {"POSSIBLE_HEADER_OFFSET", "HEADER_ROW_AMBIGUOUS"}:
            questions.append(
                "Which row should be used as the header? Candidates: "
                + ", ".join(issue.candidates)
            )
        elif issue.code == "DELIMITER_AMBIGUOUS":
            questions.append(
                "Which delimiter should be used? Candidates: " + ", ".join(issue.candidates)
            )
        elif issue.code == "MERGED_HEADER_DETECTED":
            questions.append(
                "Merged header structure was detected: "
                + ", ".join(issue.observed)
                + ". Please choose how it should be handled explicitly."
            )
        else:
            suffix = f" Candidates: {', '.join(issue.candidates)}." if issue.candidates else ""
            questions.append(f"{issue.message}{suffix} Please choose explicitly.")
    return tuple(questions)


def build_workbook_agent_summary(report) -> str:
    """Render workbook-level inspection counts before any sheet selection."""
    lines = [
        f"Workbook inspection complete: {len(report.sheets)} sheets inspected.",
        "",
        "Sheet | Regions | Merged headers | INFO | WARNING | ACTION_REQUIRED",
    ]
    for item in report.sheets:
        lines.append(
            f"{item.sheet_name} | {item.region_count} | {item.merged_header_count} | "
            f"{item.info_count} | {item.warning_count} | {item.action_required_count}"
        )
    lines.extend(
        [
            "",
            "Choose one sheet, multiple sheets, or continue with all.",
        ]
    )
    return "\n".join(lines)
