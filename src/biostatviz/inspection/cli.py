"""Terminal rendering and opt-in region selection for inspection reports."""

from __future__ import annotations

from collections.abc import Callable

from .models import InspectionReport, InspectionSeverity, TableRegion


def _severity_label(severity: InspectionSeverity) -> str:
    if severity is InspectionSeverity.ACTION_REQUIRED:
        return "ACTION REQUIRED"
    return severity.value


def format_cli_report(report: InspectionReport) -> str:
    """Render issues without modifying the report."""
    lines: list[str] = []
    region_by_id = {region.region_id: region for region in report.regions}
    for issue in report.issues:
        lines.append(f"[{_severity_label(issue.severity)}] {issue.message}")
        for index, candidate in enumerate(issue.candidates, start=1):
            region = region_by_id.get(candidate)
            if region is not None:
                preview = f" preview: {' | '.join(region.preview_values)}" if region.preview_values else ""
                lines.append(f"  {index}. {candidate} {region.a1_range}{preview}")
            else:
                lines.append(f"  {index}. {candidate}")
    return "\n".join(lines)


def resolve_cli_region(
    report: InspectionReport,
    *,
    input_fn: Callable[[str], str] = input,
) -> TableRegion | None:
    """Return an existing region chosen by 1-based index."""
    issue = next(
        (
            item
            for item in report.issues
            if item.code == "MULTIPLE_TABLE_REGIONS"
            and item.severity is InspectionSeverity.ACTION_REQUIRED
        ),
        None,
    )
    if issue is None:
        return None
    raw = input_fn("Choose table region: ").strip()
    try:
        index = int(raw)
    except ValueError as exc:
        raise ValueError("Region selection must be a 1-based integer.") from exc
    if index < 1 or index > len(issue.candidates):
        raise ValueError("Region selection is out of range.")
    region_id = issue.candidates[index - 1]
    for region in report.regions:
        if region.region_id == region_id:
            return region
    raise ValueError("Selected region is not present in the inspection report.")


def format_workbook_summary(report) -> str:
    """Render deterministic workbook summary rows in report order."""
    lines = [
        f"Workbook inspection complete: {len(report.sheets)} sheets inspected.",
        "Sheet | Regions | Merged headers | INFO | WARNING | ACTION_REQUIRED",
    ]
    for item in report.sheets:
        lines.append(
            f"{item.sheet_name} | {item.region_count} | {item.merged_header_count} | "
            f"{item.info_count} | {item.warning_count} | {item.action_required_count}"
        )
    return "\n".join(lines)


def resolve_cli_sheet_selection(
    report,
    *,
    input_fn: Callable[[str], str] = input,
) -> tuple[str, ...]:
    """Resolve `all` or comma-separated 1-based worksheet choices to sheet names."""
    raw = input_fn("Choose sheet(s) or 'all': ").strip()
    if raw.casefold() == "all":
        return report.sheet_names
    if not raw:
        raise ValueError("Sheet selection cannot be empty.")

    parts = [part.strip() for part in raw.split(",")]
    try:
        indices = [int(part) for part in parts]
    except ValueError as exc:
        raise ValueError("Sheet selection must be 'all' or comma-separated 1-based integers.") from exc

    if len(set(indices)) != len(indices):
        raise ValueError("Duplicate sheet selection is not allowed.")
    names: list[str] = []
    for index in indices:
        if index < 1 or index > len(report.sheets):
            raise ValueError("Sheet selection is out of range.")
        names.append(report.sheets[index - 1].sheet_name)
    return tuple(names)
