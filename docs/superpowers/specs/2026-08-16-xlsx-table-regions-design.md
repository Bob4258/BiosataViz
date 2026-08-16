# BioStatViz Module 01.5 Extension: XLSX Table Regions and Merged Headers

Date: 2026-08-16
Status: Proposed design, calibrated against a private real-world workbook

## 1. Goal

Extend Module 01.5 so an XLSX worksheet is not assumed to contain exactly one table. BioStatViz should detect multiple table-like regions, let Agent/CLI users select a region explicitly, and detect merged cells that participate in a selected region's header without silently expanding or interpreting them.

The motivating real-world workbook contains one worksheet with raw data, several side-by-side reorganized tables, summary blocks, and ANOVA outputs. The private workbook is used only for local validation; its scientific values must not be committed to the public repository.

## 2. Scope

This extension adds:

- XLSX table-region discovery within a worksheet.
- Region summaries with stable coordinates and bounded preview labels.
- `MULTIPLE_TABLE_REGIONS` as an `ACTION_REQUIRED` issue when more than one plausible region exists.
- Explicit region selection followed by re-inspection of only that region.
- Detection of merged cells overlapping the leading header area of the selected region.
- `MERGED_HEADER_DETECTED` as an `ACTION_REQUIRED` issue when merged header structure would make ordinary flat-column loading ambiguous.
- Agent and CLI rendering for region selection and merged-header confirmation.
- Synthetic public regression fixtures that reproduce the workbook structure without including private experimental data.

This extension does not add automatic identification of raw data versus summaries, automatic replicate labeling, automatic merged-label expansion, tidy conversion, ANOVA interpretation, or biological semantic recognition.

## 3. Selected approach

Use structural occupancy components plus conservative fragment merging. Build an occupied-cell map from raw non-empty cells plus the full extent of meaningful merged ranges, discover 4-neighbour connected components, then conservatively merge vertically aligned fragments separated by at most one fully blank row.

The approach is deterministic, language-independent, compatible with merged cells, and avoids keyword-based interpretation.

## 4. Public data contract

Add immutable `TableRegion` with stable 1-based Excel coordinates, deterministic `region:N` IDs, bounded preview evidence, merged ranges, and an `a1_range` property. Extend `InspectionReport` with `regions` and `selected_region`.

Extend XLSX inspection:

```python
inspect_table(
    path,
    sheet_name=None,
    *,
    region: TableRegion | str | None = None,
    ...,
)
```

Accepted strings are a prior `region_id` or an explicit A1 rectangle. Invalid/out-of-bounds choices raise a typed region-selection error. CSV does not accept region selection.

## 5. Region discovery algorithm

Region discovery is bounded. Default caps are 2000 rows and 256 columns. Occupied cells are raw nonblank cells or cells inside a merged range whose anchor is nonblank. Initial candidates are 4-neighbour connected components with at least two occupied cells and at least two columns.

Vertical components may merge only when they do not overlap vertically, their blank-row gap is at most one, horizontal overlap divided by the smaller width is at least 0.75, and left boundaries differ by at most one column. No horizontal gap bridging is performed. Final regions require at least two rows, two columns, and four occupied cells.

Final ordering is `(min_row, min_col, max_row, max_col)`, then IDs `region:1`, `region:2`, ... are assigned.

## 6. Multiple-region interaction

- zero regions: fall back to existing whole-sheet structural inspection;
- one region: inspect it automatically and expose `selected_region`;
- two or more regions: suppress whole-sheet blank/mixed-type analysis and emit `MULTIPLE_TABLE_REGIONS / ACTION_REQUIRED`.

The workflow is iterative: choose worksheet if needed, choose region if needed, resolve merged/header ambiguity, then proceed to loading/analysis.

## 7. Merged-header detection

After a region is selected, a merged range is header evidence when it overlaps the region, spans at least two columns, begins within the first three rows of the region, and has a nonblank anchor.

Emit:

```text
code=MERGED_HEADER_DETECTED
severity=ACTION_REQUIRED
```

Observed evidence records A1 range plus raw anchor value. BioStatViz does not infer that spanned columns are biological replicates and does not automatically flatten or suffix them.

## 8. Preview and coordinates

`read_xlsx_preview()` preserves meaningful merged-range metadata. `TablePreview` carries merged ranges plus `origin_row`/`origin_col`; cropping retains original source coordinates so issue locations remain real Excel coordinates.

## 9. Agent and CLI behavior

For multiple regions, render region ID, A1 range, and bounded preview evidence. Agent asks which region to inspect and never chooses based on terms such as summary/statistical labels. CLI returns an existing region selection rather than reconstructing coordinates from semantic text.

For merged headers, render the ranges and ask for explicit handling; core inspection never answers the semantic question.

## 10. Testing strategy

All implementation follows TDD using synthetic XLSX fixtures only. Required coverage includes deterministic region rectangles, side-by-side separation, one-row vertical merging, two-row separation, merged occupancy, multiple-region suppression of whole-sheet quality checks, selected-region inspection, merged-header detection, source-byte immutability, and regression of ordinary CSV/XLSX behavior.

The private workbook remains local-only and is never added to repository fixtures.

## 11. Private workbook acceptance target

A private real-world workbook is a local acceptance dataset only; its filename and scientific labels are intentionally omitted from the public specification.

Expected behavior: multiple regions are detected rather than treating the whole worksheet as one dataframe; whole-sheet blank/mixed-type noise is suppressed before region selection; selecting the raw block exposes its merged header ranges; no biological meaning is assigned automatically.

## 12. Acceptance criteria

1. XLSX worksheets can expose deterministic `TableRegion` objects.
2. Multiple regions require explicit selection instead of whole-sheet quality analysis.
3. Selected-region inspection uses original Excel coordinates.
4. Merged header ranges are detected before flat dataframe loading.
5. Merged-header interpretation is never automatic.
6. Agent and CLI consume the same region/report contract.
7. Synthetic regression data contains no private scientific results.
8. Private local acceptance materially reduces false blank/mixed-type warnings before selection.
9. Existing Module 01/01.5 regressions remain green.
10. No Module 02 statistical inference or biological semantics are introduced.
