"""Deterministic XLSX table-region discovery from raw occupied geometry."""

from __future__ import annotations

from dataclasses import dataclass

from .models import TableRegion
from .preview import TablePreview


@dataclass(frozen=True, slots=True)
class _Fragment:
    cells: frozenset[tuple[int, int]]

    @property
    def min_row(self) -> int:
        return min(row for row, _ in self.cells)

    @property
    def max_row(self) -> int:
        return max(row for row, _ in self.cells)

    @property
    def min_col(self) -> int:
        return min(col for _, col in self.cells)

    @property
    def max_col(self) -> int:
        return max(col for _, col in self.cells)

    @property
    def width(self) -> int:
        return self.max_col - self.min_col + 1

    @property
    def height(self) -> int:
        return self.max_row - self.min_row + 1


def _is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _scan_bounds(preview: TablePreview) -> tuple[int, int, int, int]:
    row_count = len(preview.rows)
    column_count = max((len(row) for row in preview.rows), default=0)
    return (
        preview.origin_row,
        preview.origin_row + row_count - 1,
        preview.origin_col,
        preview.origin_col + column_count - 1,
    )


def _occupied_cells(preview: TablePreview) -> set[tuple[int, int]]:
    occupied: set[tuple[int, int]] = set()
    for row_offset, row in enumerate(preview.rows):
        source_row = preview.origin_row + row_offset
        for col_offset, value in enumerate(row):
            if not _is_blank(value):
                occupied.add((source_row, preview.origin_col + col_offset))

    if not preview.rows:
        return occupied
    min_row, max_row, min_col, max_col = _scan_bounds(preview)
    for merged in preview.merged_ranges:
        overlap_min_row = max(min_row, merged.min_row)
        overlap_max_row = min(max_row, merged.max_row)
        overlap_min_col = max(min_col, merged.min_col)
        overlap_max_col = min(max_col, merged.max_col)
        if overlap_min_row > overlap_max_row or overlap_min_col > overlap_max_col:
            continue
        for row in range(overlap_min_row, overlap_max_row + 1):
            for col in range(overlap_min_col, overlap_max_col + 1):
                occupied.add((row, col))
    return occupied


def _row_bands(occupied: set[tuple[int, int]]) -> list[tuple[int, int]]:
    rows = sorted({row for row, _ in occupied})
    if not rows:
        return []

    bands: list[tuple[int, int]] = []
    band_start = rows[0]
    previous = rows[0]
    for row in rows[1:]:
        if row == previous + 1:
            previous = row
            continue
        bands.append((band_start, previous))
        band_start = previous = row
    bands.append((band_start, previous))
    return bands


def _column_bands(
    occupied: set[tuple[int, int]],
    *,
    min_row: int,
    max_row: int,
) -> list[tuple[int, int]]:
    columns = sorted({col for row, col in occupied if min_row <= row <= max_row})
    if not columns:
        return []

    bands: list[tuple[int, int]] = []
    band_start = columns[0]
    previous = columns[0]
    for col in columns[1:]:
        # col - previous == 2 means exactly one blank spacer column.
        # Keep that spacer inside the same table region.
        if col - previous <= 2:
            previous = col
            continue
        bands.append((band_start, previous))
        band_start = previous = col
    bands.append((band_start, previous))
    return bands


def _segmented_fragments(occupied: set[tuple[int, int]]) -> list[_Fragment]:
    fragments: list[_Fragment] = []
    for min_row, max_row in _row_bands(occupied):
        for min_col, max_col in _column_bands(
            occupied, min_row=min_row, max_row=max_row
        ):
            cells = frozenset(
                (row, col)
                for row, col in occupied
                if min_row <= row <= max_row and min_col <= col <= max_col
            )
            if cells:
                fragments.append(_Fragment(cells))
    return sorted(
        fragments,
        key=lambda f: (f.min_row, f.min_col, f.max_row, f.max_col),
    )


def _value_at(preview: TablePreview, row: int, col: int) -> object:
    row_offset = row - preview.origin_row
    col_offset = col - preview.origin_col
    if row_offset < 0 or row_offset >= len(preview.rows):
        return None
    source_row = preview.rows[row_offset]
    if col_offset < 0 or col_offset >= len(source_row):
        return None
    return source_row[col_offset]


def _preview_values(preview: TablePreview, fragment: _Fragment) -> tuple[str, ...]:
    values: list[str] = []
    seen: set[str] = set()
    for row, col in sorted(fragment.cells):
        value = _value_at(preview, row, col)
        if _is_blank(value):
            continue
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            values.append(text)
            if len(values) >= 6:
                break
    return tuple(values)


def _overlaps(fragment: _Fragment, min_row: int, max_row: int, min_col: int, max_col: int) -> bool:
    return not (
        fragment.max_row < min_row
        or fragment.min_row > max_row
        or fragment.max_col < min_col
        or fragment.min_col > max_col
    )


def discover_regions(preview: TablePreview) -> tuple[tuple[TableRegion, ...], bool]:
    """Discover deterministic table-like rectangles from occupied XLSX cells."""
    occupied = _occupied_cells(preview)
    fragments = _segmented_fragments(occupied)
    finals = [
        fragment
        for fragment in fragments
        if fragment.height >= 2 and fragment.width >= 2 and len(fragment.cells) >= 4
    ]
    finals.sort(key=lambda f: (f.min_row, f.min_col, f.max_row, f.max_col))

    regions: list[TableRegion] = []
    for index, fragment in enumerate(finals, start=1):
        merged_ranges = tuple(
            merged.a1_range
            for merged in preview.merged_ranges
            if _overlaps(
                fragment,
                merged.min_row,
                merged.max_row,
                merged.min_col,
                merged.max_col,
            )
        )
        regions.append(
            TableRegion(
                region_id=f"region:{index}",
                sheet_name=preview.sheet_name or "",
                min_row=fragment.min_row,
                max_row=fragment.max_row,
                min_col=fragment.min_col,
                max_col=fragment.max_col,
                non_empty_cells=len(fragment.cells),
                preview_values=_preview_values(preview, fragment),
                merged_ranges=merged_ranges,
            )
        )

    scanned_rows = len(preview.rows)
    scanned_columns = max((len(row) for row in preview.rows), default=0)
    scan_last_row = preview.origin_row + scanned_rows - 1 if scanned_rows else 0
    scan_last_col = preview.origin_col + scanned_columns - 1 if scanned_columns else 0
    truncated = (
        preview.apparent_rows > scan_last_row
        or preview.apparent_columns > scan_last_col
    )
    return tuple(regions), truncated
