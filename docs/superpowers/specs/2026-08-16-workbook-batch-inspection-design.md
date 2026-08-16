# BioStatViz Module 01.5 Extension: Workbook Batch Inspection Design

Date: 2026-08-16
Status: Approved behavior, pending implementation plan

## 1. Goal

Extend Module 01.5 so an XLSX workbook can be inspected as a collection of independent scientific data sheets. By default, BioStatViz inspects every worksheet, returns one workbook-level summary, lists the status of every sheet, and then allows Agent/CLI callers to let the user choose one or more sheets for deeper inspection or analysis.

At the same time, harden XLSX geometry detection so empty merged ranges and style-only spreadsheet residue do not create phantom table regions or false scan-truncation warnings.

## 2. User-facing behavior

Default workflow:

```text
XLSX workbook
    |
    v
inspect_workbook(path)
    |
    +-- inspect every worksheet in workbook order
    +-- preserve each sheet's independent InspectionReport
    +-- build a workbook-level summary
    |
    v
WorkbookInspectionReport
    |
    +-- list all sheets and statuses
    +-- region count per sheet
    +-- merged-header count per sheet
    +-- INFO / WARNING / ACTION_REQUIRED counts
    |
    v
Agent / CLI summary
    |
    v
user may choose one sheet, multiple sheets, or continue with all
```

The default is **inspect all sheets first**. Selection is a later interaction step; it does not gate the initial workbook inspection.

Optional narrowed use is also supported:

```python
inspect_workbook(path, sheets=["2b", "2d", "2i"])
```

This explicitly restricts which sheets are inspected but does not change the default behavior.

## 3. Core design principles

### 3.1 A workbook may contain many valid independent tables

`inspect_workbook()` must not reuse the single-table assumption that "multiple plausible sheets means choose exactly one primary sheet". It explicitly treats selected worksheets as independent inspection targets.

`inspect_table()` remains the single-sheet/single-target entry point. Its existing behavior is not removed.

### 3.2 Inspect all first, select later

The workbook core performs deterministic inspection of all selected sheets and returns the results. It does not prompt and does not choose a preferred sheet.

Agent/CLI adapters render the summary and may then ask the user which sheet(s) to continue with.

### 3.3 Empty merged ranges are formatting residue

A merged range participates in XLSX structural geometry only when its top-left anchor cell contains a nonblank value.

Examples:

```text
C3:G3 anchor = "PBS"   -> structural merged range
M26:Q26 anchor = blank -> ignore completely
```

An ignored empty merged range:

- does not expand occupied geometry;
- does not create a table region;
- does not count as a merged header;
- does not contribute to scan-truncation detection.

### 3.4 Effective worksheet geometry is value-based

Do not use `worksheet.max_row` or `worksheet.max_column` as evidence that meaningful data exists at those coordinates, because styles, formatting, validation, or historical edits may inflate them.

Define meaningful occupied geometry as the union of:

1. cells whose value is nonblank; and
2. full merged-range rectangles whose anchor value is nonblank.

The effective maximum row/column and truncation detection are computed from this meaningful geometry.

### 3.5 No biological semantics

Workbook inspection may report sheet names such as figure-panel labels, but it must not infer that a sheet name represents a figure, experimental group, replicate, control, time point, or biological endpoint.

## 4. Public API

### 4.1 `inspect_workbook`

Proposed public entry point:

```python
def inspect_workbook(
    path: str | Path,
    *,
    sheets: Sequence[str | int] | None = None,
    max_rows: int = 50,
    max_columns: int = 50,
) -> WorkbookInspectionReport:
    ...
```

For Module 01.5 this function accepts `.xlsx` only. Passing CSV raises `UnsupportedTableFormatError` rather than silently treating a CSV as a one-sheet workbook.

Behavior:

- `sheets=None`: inspect every worksheet, in workbook order;
- `sheets=[...]`: inspect only those explicit selectors, preserving the caller's order;
- duplicate selectors are rejected rather than silently deduplicated;
- missing string names or invalid integer indices raise `ExcelSheetNotFoundError`;
- every chosen sheet is inspected by the existing single-sheet inspection path with an explicit sheet selector, so workbook-level processing never triggers `MULTIPLE_PLAUSIBLE_SHEETS` merely because multiple worksheets exist.

### 4.2 `WorkbookSheetResult`

Immutable model:

```python
@dataclass(frozen=True, slots=True)
class WorkbookSheetResult:
    sheet_name: str
    report: InspectionReport

    @property
    def info_count(self) -> int: ...

    @property
    def warning_count(self) -> int: ...

    @property
    def action_required_count(self) -> int: ...

    @property
    def region_count(self) -> int: ...

    @property
    def merged_header_count(self) -> int: ...
```

Counts are derived from the contained `InspectionReport`; they are not separately mutable state.

`region_count` is based on the report's discovered regions. `merged_header_count` is derived from `MERGED_HEADER_DETECTED` issue evidence: it is the number of distinct A1 merged ranges recorded in that issue. Empty merged ranges never contribute.

### 4.3 `WorkbookInspectionReport`

Immutable model:

```python
@dataclass(frozen=True, slots=True)
class WorkbookInspectionReport:
    source_path: Path
    sheets: tuple[WorkbookSheetResult, ...]

    @property
    def sheet_names(self) -> tuple[str, ...]: ...

    @property
    def has_warnings(self) -> bool: ...

    @property
    def requires_user_input(self) -> bool: ...
```

`requires_user_input` is true when any contained sheet report has an `ACTION_REQUIRED` issue. This is a summary signal only. It does **not** mean workbook inspection should stop before other sheets are inspected.

## 5. Workbook summary and selection adapters

### 5.1 Agent summary

Add a workbook-specific renderer, for example:

```python
build_workbook_agent_summary(report) -> str
```

It presents summary first, then sheet names. It does not choose sheets.

Target content:

```text
Workbook inspection complete: 11 sheets inspected.

Sheet  Regions  Merged headers  INFO  WARNING  ACTION_REQUIRED
2b     1        2               0     0        1
2d     1        2               0     0        1
...

Choose one sheet, multiple sheets, or continue with all.
```

Exact whitespace/layout may differ by adapter, but the factual content and order must remain deterministic.

### 5.2 CLI summary

Add:

```python
format_workbook_summary(report) -> str
```

It shows the same core fields in workbook order.

An opt-in selector may accept:

- `all` -> every sheet name;
- one 1-based sheet number -> one sheet;
- comma-separated 1-based numbers -> multiple sheets.

The selection helper returns sheet names only. It does not modify the report and does not perform analysis itself.

### 5.3 Python users

Python users can consume the full report directly:

```python
report = inspect_workbook("source_data.xlsx")

for item in report.sheets:
    print(item.sheet_name, item.report.requires_user_input)
```

No prompt occurs in core Python APIs.

## 6. Empty merged-range filtering

### 6.1 Blank definition

An anchor is blank when:

```python
value is None
```

or it is a string whose `.strip()` is empty.

Numeric zero, boolean `False`, and formulas are nonblank values and therefore count as meaningful anchors.

### 6.2 Preview contract

The XLSX preview layer should expose only meaningful merged ranges to downstream region/header detection, or explicitly distinguish meaningful from ignored ranges so downstream consumers cannot accidentally treat empty ranges as occupied.

Preferred contract: filter them once at the preview boundary.

### 6.3 Effective bounds

Effective bounds are calculated from raw nonblank cells plus meaningful merged-range rectangles.

For the observed real-world pattern:

```text
worksheet.max_row = 108
worksheet.max_column = 28
actual nonblank cell bbox = B2:L7
empty merged ranges below row 7 = ignored
```

The effective occupied extent must remain `B2:L7`; it must not become row 108/column 28.

## 7. Interaction with existing table-region detection

Existing table-region rules remain in force after meaningful geometry is filtered:

- side-by-side disconnected regions remain separate;
- vertically aligned fragments separated by one blank row may be conservatively merged according to the existing rule;
- two or more blank rows keep regions separate;
- meaningful merged-header spans participate in region width;
- empty merged ranges do not participate at all.

If one sheet has multiple regions, its individual `InspectionReport` may still contain `MULTIPLE_TABLE_REGIONS / ACTION_REQUIRED`. Workbook inspection records that status and continues inspecting all remaining sheets.

## 8. Error handling

Separate workbook-level failures from sheet-level inspection issues.

### Exceptions

- source path missing -> existing `TableNotFoundError`;
- non-XLSX format -> `UnsupportedTableFormatError`;
- workbook unreadable -> existing/compatible typed read error;
- explicit selected sheet missing -> `ExcelSheetNotFoundError`;
- duplicate sheet selectors -> `ValueError` with an explicit duplicate-selector message.

### Issues

Structural ambiguity within an inspected sheet remains an `InspectionIssue`, not an exception. One sheet's `ACTION_REQUIRED` issue never prevents inspection of later sheets.

## 9. Determinism and ordering

- Default workbook result order exactly matches Excel workbook sheet order.
- Explicit `sheets=[...]` result order exactly matches caller order.
- Issue ordering within each sheet remains the existing deterministic order.
- Summary renderers preserve `WorkbookInspectionReport.sheets` order.
- No parallel execution is required in the first implementation; sequential inspection is preferred for deterministic, simple behavior.

## 10. Testing strategy

Implementation follows TDD and uses only synthetic fixtures in the repository.

### Empty merged-range regression fixture

Create an anonymous workbook with:

- one real table in `B2:L7`;
- two nonblank merged headers inside the table;
- several empty merged ranges far below/right of the table;
- optional style-only cells beyond the true data.

Required assertions:

- exactly one meaningful table region is detected;
- only the two nonblank merged ranges are reported;
- no phantom region is detected below the table;
- no false `REGION_SCAN_TRUNCATED` appears;
- effective bounds reflect meaningful values rather than `ws.max_row/max_column`.

### Workbook batch fixture

Create an anonymous workbook with at least four structurally different sheets:

1. ordinary single table;
2. single table with two meaningful merged headers;
3. table with three meaningful merged headers;
4. sheet containing multiple table regions.

Required assertions:

- default `inspect_workbook()` inspects all four sheets;
- workbook order is preserved;
- sheet 4 can have `ACTION_REQUIRED` while sheets 1-3 are still inspected;
- per-sheet summary counts are correct;
- explicit subset selection works and preserves caller order;
- invalid and duplicate selectors fail explicitly;
- source bytes are unchanged.

### Adapter tests

- Agent summary lists all inspected sheets after the workbook summary;
- CLI summary uses the same report contract;
- selector can return all, one, or multiple sheet names;
- adapter selection never mutates or re-inspects the workbook.

### Privacy test

No real Nature workbook bytes, figure labels, experimental labels, article identifiers, or file names are committed to repository fixtures. Real files may be used only for local acceptance.

## 11. Acceptance criteria

The extension is complete when:

1. `inspect_workbook()` inspects every worksheet by default.
2. Workbook results are summarized before user sheet selection.
3. Users may subsequently select one, multiple, or all sheets via adapters.
4. Explicit `sheets=[...]` restricts inspection and preserves requested order.
5. Multiple independent worksheets are not treated as an error or forced single-choice ambiguity.
6. One sheet's `ACTION_REQUIRED` issues do not prevent other sheets from being inspected.
7. Empty merged ranges do not affect occupied geometry, table regions, merged-header counts, or truncation status.
8. Style-only worksheet extent does not create meaningful occupied geometry.
9. Existing single-sheet `inspect_table()` behavior remains backward compatible.
10. All pre-existing Module 01/01.5 tests remain green.
11. Core APIs remain deterministic, non-interactive, and free of LLM/MCP dependencies.
12. Real private/publication data is not committed as a repository fixture.

## 12. Local real-data acceptance target

The uploaded Nature Source Data workbook is used only as a local validation target, not a fixture.

Observed workbook properties used to validate the design:

- 11 worksheets;
- several sheets contain meaningful merged group headers;
- at least one sheet has Excel metadata/format extent much larger than its actual nonblank data;
- empty merged ranges exist outside the true data area.

Expected local behavior after implementation:

- all 11 sheets are inspected in workbook order by default;
- the workbook summary lists all 11 sheet names;
- empty merged/style residue does not create phantom regions;
- each sheet retains its own independent `InspectionReport`;
- the user can then select one, multiple, or all sheet names for the next workflow step.
