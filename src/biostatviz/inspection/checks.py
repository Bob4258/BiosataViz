"""Pure structural and basic data-quality checks for raw table previews."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace

from biostatviz.io import LoadingOptions

from .models import InspectionIssue, InspectionSeverity
from .preview import TablePreview


@dataclass(frozen=True, slots=True)
class StructuralAnalysis:
    header_row: int | None
    shape_preview: tuple[int, int]
    issues: tuple[InspectionIssue, ...]
    candidate_loading_options: tuple[LoadingOptions, ...]


def _is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _text_like(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return False
    try:
        float(text)
    except ValueError:
        return True
    return False


def _norm(value: object) -> str:
    return str(value).strip().casefold()


def _candidate_metrics(rows: tuple[tuple[object, ...], ...], index: int):
    row = rows[index]
    values = [value for value in row if not _is_blank(value)]
    non_empty_count = len(values)
    if non_empty_count < 2:
        return None
    text_count = sum(_text_like(value) for value in values)
    if text_count / non_empty_count < 0.5:
        return None
    following = 0
    for later in rows[index + 1 : index + 4]:
        count = sum(not _is_blank(value) for value in later)
        if count >= 2:
            following += 1
    if following == 0:
        return None
    labels = [_norm(value) for value in values]
    unique = len(set(labels)) == len(labels)
    score = non_empty_count + (2 if unique else 0) + text_count + min(following, 3)
    return score, unique


def _shape(rows: tuple[tuple[object, ...], ...]) -> tuple[int, int]:
    return len(rows), max((len(row) for row in rows), default=0)


def inspect_structure(preview: TablePreview, *, base_options: LoadingOptions) -> StructuralAnalysis:
    """Inspect bounded raw rows for header and blank structure ambiguity."""
    rows = preview.rows
    scored: list[tuple[int, int, bool]] = []
    for index in range(min(len(rows), 10)):
        metrics = _candidate_metrics(rows, index)
        if metrics is not None:
            score, unique = metrics
            scored.append((index, score, unique))

    issues: list[InspectionIssue] = []
    candidates: list[LoadingOptions] = []
    header_row: int | None = None
    if not scored:
        issues.append(InspectionIssue(code="HEADER_NOT_DETERMINED", severity=InspectionSeverity.ACTION_REQUIRED, message="No plausible header row could be determined from the bounded preview.", suggested_action="Choose the header row explicitly."))
    else:
        best_score = max(score for _, score, _ in scored)
        best_rows = [index for index, score, _ in scored if score == best_score]
        if len(best_rows) > 1:
            issues.append(InspectionIssue(code="HEADER_ROW_AMBIGUOUS", severity=InspectionSeverity.ACTION_REQUIRED, message="Multiple rows are equally plausible headers.", candidates=tuple(f"row:{row}" for row in best_rows), suggested_action="Choose the header row explicitly."))
            candidates.extend(replace(base_options, header=row) for row in best_rows)
        else:
            header_row = best_rows[0]
            if header_row != 0:
                issues.append(InspectionIssue(code="POSSIBLE_HEADER_OFFSET", severity=InspectionSeverity.ACTION_REQUIRED, message="A later row is a stronger header candidate than the first row.", candidates=(f"row:{header_row}",), suggested_action="Confirm the header row explicitly."))
                candidates.append(replace(base_options, header=header_row))
            header_values = [value for value in rows[header_row] if not _is_blank(value)]
            normalized = [_norm(value) for value in header_values]
            counts = Counter(normalized)
            duplicate_norms = {key for key, count in counts.items() if count > 1}
            if duplicate_norms:
                seen: set[str] = set(); observed: list[str] = []
                for value in header_values:
                    norm = _norm(value)
                    if norm in duplicate_norms and norm not in seen:
                        seen.add(norm); observed.append(str(value).strip())
                issues.append(InspectionIssue(code="DUPLICATE_COLUMN_NAMES", severity=InspectionSeverity.ACTION_REQUIRED, message="Duplicate raw column labels make downstream references ambiguous.", observed=tuple(observed), location=f"row:{header_row}"))
            last_nonblank_row = header_row
            for index in range(header_row + 1, len(rows)):
                if any(not _is_blank(value) for value in rows[index]): last_nonblank_row = index
            data_rows = rows[header_row + 1:last_nonblank_row + 1]
            blank_row_indices = [header_row + 1 + offset for offset, row in enumerate(data_rows) if all(_is_blank(value) for value in row)]
            if blank_row_indices:
                severity = InspectionSeverity.INFO if len(blank_row_indices) == 1 else InspectionSeverity.WARNING
                issues.append(InspectionIssue(code="BLANK_ROW", severity=severity, message="Blank row(s) occur inside the apparent table region.", observed=tuple(str(index) for index in blank_row_indices)))
            width = max((len(row) for row in rows[header_row:last_nonblank_row + 1]), default=0)
            occupied_columns = [column for column in range(width) if any(column < len(row) and not _is_blank(row[column]) for row in rows[header_row:last_nonblank_row + 1])]
            if occupied_columns:
                first, last = min(occupied_columns), max(occupied_columns)
                blank_columns = [column for column in range(first, last + 1) if all(column >= len(row) or _is_blank(row[column]) for row in rows[header_row:last_nonblank_row + 1])]
                if blank_columns:
                    issues.append(InspectionIssue(code="BLANK_COLUMN", severity=InspectionSeverity.WARNING, message="Blank column(s) occur inside the apparent table region.", observed=tuple(str(column) for column in blank_columns)))
    return StructuralAnalysis(header_row=header_row, shape_preview=_shape(rows), issues=tuple(issues), candidate_loading_options=tuple(candidates))


PLACEHOLDER_TOKENS = {"nd", "na", "n/a", "-"}
IDENTIFIER_HEADERS = {"sample", "sample_id", "sample id", "id", "name", "sample_name", "sample name"}


def _is_numeric_like(value: object) -> bool:
    if isinstance(value, bool): return False
    if isinstance(value, (int, float)): return True
    if isinstance(value, str):
        text = value.strip()
        if not text: return False
        try: float(text)
        except ValueError: return False
        return True
    return False


def _distinct_first(values: list[str], limit: int = 10) -> tuple[str, ...]:
    result: list[str] = []; seen: set[str] = set()
    for value in values:
        if value in seen: continue
        seen.add(value); result.append(value)
        if len(result) >= limit: break
    return tuple(result)


def inspect_quality(preview: TablePreview, *, header_row: int) -> tuple[InspectionIssue, ...]:
    """Report basic value-quality evidence without coercing or cleaning values."""
    if header_row >= len(preview.rows): return ()
    headers = preview.rows[header_row]; data_rows = preview.rows[header_row + 1:]
    width = max((len(row) for row in preview.rows[header_row:]), default=0)
    issues: list[InspectionIssue] = []
    for column in range(width):
        raw_header = headers[column] if column < len(headers) else ""
        header = str(raw_header).strip() if not _is_blank(raw_header) else f"column_{column}"
        values = [row[column] if column < len(row) else None for row in data_rows]
        blank_count = sum(_is_blank(value) for value in values)
        if blank_count:
            issues.append(InspectionIssue(code="BLANK_VALUES_PRESENT", severity=InspectionSeverity.INFO, message=f"Column {header!r} contains {blank_count} blank value(s).", location=f"column:{header}", observed=(f"count:{blank_count}",)))
        nonblank = [value for value in values if not _is_blank(value)]
        if nonblank:
            numeric = [value for value in nonblank if _is_numeric_like(value)]
            if len(numeric) >= 2 and len(numeric) / len(nonblank) >= 0.60:
                unexpected = [value for value in nonblank if not _is_numeric_like(value)]
                if unexpected:
                    unexpected_text = [str(value).strip() for value in unexpected]
                    normalized = {value.casefold() for value in unexpected_text}
                    if normalized.issubset(PLACEHOLDER_TOKENS):
                        code = "PLACEHOLDER_TOKEN_IN_NUMERIC_COLUMN"; message = f"Numeric-looking column {header!r} contains {len(unexpected)} placeholder-like text value(s)."
                    else:
                        code = "MIXED_NUMERIC_TEXT"; message = f"Numeric-looking column {header!r} contains {len(unexpected)} unexpected text value(s)."
                    issues.append(InspectionIssue(code=code, severity=InspectionSeverity.WARNING, message=message, location=f"column:{header}", observed=_distinct_first(unexpected_text)))
        if _norm(header) in IDENTIFIER_HEADERS:
            text_values = [str(value).strip() for value in nonblank]; counts = Counter(text_values)
            observed = _distinct_first([value for value in text_values if counts[value] > 1])
            if observed:
                issues.append(InspectionIssue(code="POSSIBLE_DUPLICATE_IDENTIFIER", severity=InspectionSeverity.WARNING, message="Identifier-like column contains repeated values.", location=f"column:{header}", observed=observed))
    return tuple(issues)
