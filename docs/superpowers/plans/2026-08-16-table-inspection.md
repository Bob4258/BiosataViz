# BioStatViz Module 01.5: Table Inspection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic structural-inspection and basic data-quality layer for imperfect scientific CSV/XLSX files, shared by Agent/MCP and CLI workflows, without silently changing scientific meaning.

**Architecture:** Keep Module 01 as the deterministic loader and add a new `biostatviz.inspection` package that reads bounded raw previews before pandas semantic coercion, produces structured `InspectionReport` objects, and separates core inspection from interaction adapters. Explicit user decisions are represented as `LoadingOptions` and passed back to Module 01; the inspection core never prompts, calls an LLM, or mutates source data.

**Tech Stack:** Python 3.11, uv, pandas 2.2.x, openpyxl 3.1.x, Python standard-library `csv`, pytest 8.x, Git.

## Global Constraints

- Primary local OS: Windows.
- Python version: 3.11.
- Package/environment manager: uv.
- Testing framework: pytest.
- Version control: Git.
- Supported input formats remain `.csv` and `.xlsx` only.
- Inspection must never modify the source file.
- Inspection must preserve enough raw representation to detect user-authored tokens before pandas default NA/type coercion hides them.
- `inspect_table()` is deterministic and non-interactive.
- The inspection core contains no `input()`, terminal UI, MCP transport, LLM call, or arbitrary Python execution.
- Risk levels are exactly `INFO`, `WARNING`, and `ACTION_REQUIRED`.
- `ACTION_REQUIRED` means BioStatViz must not choose the ambiguous interpretation for the user.
- Default behavior performs no automatic data cleaning.
- `ND`, `NA`, `N/A`, `-`, and similar observed tokens are reported, not assigned biological meaning.
- No control/treatment inference, replicate inference, statistical-test selection, outlier removal, imputation, normalization, scaling, batch correction, or general dataset profiling is implemented here.
- Module 02 remains responsible for statistical Dataset Profiling.
- All implementation work follows TDD: write one failing behavior test, verify RED, implement the minimum, verify GREEN, then refactor only while green.
- Existing Module 01 tests must remain green after every task that touches loading behavior.

---

## File Structure Produced by This Plan

```text
biostatviz/
├── README.md
├── src/
│   └── biostatviz/
│       ├── io/
│       │   ├── __init__.py          # export LoadingOptions + load_table
│       │   ├── loader.py            # explicit deterministic loading options
│       │   └── models.py            # LoadedTable + LoadingOptions
│       └── inspection/
│           ├── __init__.py          # public inspection API
│           ├── errors.py            # typed inspection failures
│           ├── models.py            # severity, issues, summaries, reports
│           ├── preview.py           # raw bounded CSV/XLSX preview readers
│           ├── checks.py            # pure structural + quality checks
│           ├── inspector.py         # inspect_table orchestration
│           ├── agent.py             # Agent-facing question rendering
│           └── cli.py               # CLI rendering + interactive resolution helper
└── tests/
    └── unit/
        ├── io/
        │   ├── test_csv_loader.py
        │   ├── test_excel_loader.py
        │   └── test_loading_options.py
        └── inspection/
            ├── test_models.py
            ├── test_preview_csv.py
            ├── test_preview_xlsx.py
            ├── test_structural_checks.py
            ├── test_quality_checks.py
            ├── test_inspector.py
            └── test_adapters.py
```

Responsibilities:

- `io/models.py`: explicit user-confirmed loading configuration only.
- `io/loader.py`: deterministic final loading, no inspection heuristics.
- `inspection/models.py`: stable cross-adapter data contract.
- `inspection/preview.py`: raw bounded representation and delimiter/sheet discovery.
- `inspection/checks.py`: pure functions that turn raw preview rows into structured issues.
- `inspection/inspector.py`: file validation, preview selection, sheet ambiguity, and report assembly.
- `inspection/agent.py`: convert `ACTION_REQUIRED` issues into structured human questions without making choices.
- `inspection/cli.py`: terminal formatting and opt-in interactive choice collection; it may call `input()` only in this adapter.

---

### Task 1: Make Module 01 accept explicit loading decisions and preserve user-authored NA-like tokens

**Files:**
- Modify: `src/biostatviz/io/models.py`
- Modify: `src/biostatviz/io/loader.py`
- Modify: `src/biostatviz/io/__init__.py`
- Modify: `tests/unit/io/test_csv_loader.py`
- Modify: `tests/unit/io/test_excel_loader.py`
- Create: `tests/unit/io/test_loading_options.py`

**Interfaces:**
- Consumes: existing `load_table(path, sheet_name=None)` behavior.
- Produces:
  - `LoadingOptions(sheet_name, header, delimiter, encoding, keep_default_na)`.
  - `load_table(path, sheet_name=None, *, options: LoadingOptions | None = None) -> LoadedTable`.
  - Existing callers using `load_table(path)` or `load_table(path, sheet_name="Data")` remain valid.

- [ ] **Step 1: Write failing tests for raw NA-like token preservation**

Create `tests/unit/io/test_loading_options.py`:

```python
from pathlib import Path

from biostatviz.io import load_table


def test_csv_preserves_user_authored_na_like_tokens_by_default(tmp_path: Path):
    path = tmp_path / "tokens.csv"
    path.write_text(
        "sample,value\n"
        "S1,10\n"
        "S2,NA\n"
        "S3,N/A\n"
        "S4,-\n",
        encoding="utf-8",
    )

    loaded = load_table(path)

    assert loaded.data["value"].tolist() == ["10", "NA", "N/A", "-"]
```

Update the existing CSV missing-value test so the expected dataframe is read with `keep_default_na=False` rather than pandas defaults:

```python
expected = pd.read_csv(csv_path, keep_default_na=False)
```

- [ ] **Step 2: Run the preservation test and verify RED**

```powershell
uv run pytest tests/unit/io/test_loading_options.py::test_csv_preserves_user_authored_na_like_tokens_by_default -v
```

Expected: FAIL because current `load_table()` allows pandas to convert `NA`/`N/A` to missing values.

- [ ] **Step 3: Add the explicit loading contract**

Add to `src/biostatviz/io/models.py`:

```python
@dataclass(frozen=True, slots=True)
class LoadingOptions:
    """Explicit deterministic choices used when loading a table."""

    sheet_name: str | int | None = None
    header: int | None = 0
    delimiter: str = ","
    encoding: str = "utf-8-sig"
    keep_default_na: bool = False
```

- [ ] **Step 4: Change `load_table()` to use `LoadingOptions` without breaking the legacy `sheet_name` argument**

Implement this resolution pattern near the top of `load_table()`:

```python
if options is not None and sheet_name is not None:
    raise TableReadError(
        "Pass Excel sheet selection either with sheet_name or LoadingOptions, not both."
    )

resolved = options or LoadingOptions(sheet_name=sheet_name)
```

Change the function signature to:

```python
def load_table(
    path: str | Path,
    sheet_name: str | int | None = None,
    *,
    options: LoadingOptions | None = None,
) -> LoadedTable:
```

For CSV use:

```python
data = pd.read_csv(
    source_path,
    sep=resolved.delimiter,
    encoding=resolved.encoding,
    header=resolved.header,
    keep_default_na=resolved.keep_default_na,
)
```

Reject `resolved.sheet_name is not None` for CSV.

For XLSX use:

```python
requested_sheet = 0 if resolved.sheet_name is None else resolved.sheet_name

data = pd.read_excel(
    source_path,
    sheet_name=requested_sheet,
    header=resolved.header,
    keep_default_na=resolved.keep_default_na,
    engine="openpyxl",
)
```

- [ ] **Step 5: Export `LoadingOptions`**

Add it to `src/biostatviz/io/__init__.py` and `__all__`.

- [ ] **Step 6: Add explicit delimiter/header tests**

Append to `tests/unit/io/test_loading_options.py`:

```python
from biostatviz.io import LoadingOptions


def test_csv_applies_explicit_delimiter_and_header(tmp_path: Path):
    path = tmp_path / "semicolon.csv"
    path.write_text(
        "experiment note\n"
        "sample;value\n"
        "S1;10\n"
        "S2;20\n",
        encoding="utf-8",
    )

    loaded = load_table(
        path,
        options=LoadingOptions(delimiter=";", header=1),
    )

    assert loaded.data.columns.tolist() == ["sample", "value"]
    assert loaded.data["sample"].tolist() == ["S1", "S2"]
```

Add conflict coverage:

```python
import pytest
from biostatviz.io import TableReadError


def test_load_table_rejects_duplicate_sheet_configuration(tmp_path: Path):
    path = tmp_path / "book.xlsx"
    pd.DataFrame({"x": [1]}).to_excel(path, index=False, engine="openpyxl")

    with pytest.raises(TableReadError, match="either with sheet_name or LoadingOptions"):
        load_table(path, sheet_name="Sheet1", options=LoadingOptions(sheet_name="Sheet1"))
```

- [ ] **Step 7: Run Module 01 tests**

```powershell
uv run pytest tests/unit/io -v
```

Expected: all Module 01 tests PASS.

- [ ] **Step 8: Commit**

```powershell
git add src/biostatviz/io tests/unit/io
git commit -m "feat: add explicit table loading options"
```

---

### Task 2: Define the inspection data contracts and typed failures

**Files:**
- Create: `src/biostatviz/inspection/__init__.py`
- Create: `src/biostatviz/inspection/errors.py`
- Create: `src/biostatviz/inspection/models.py`
- Create: `tests/unit/inspection/test_models.py`

**Interfaces:**
- Consumes: `LoadingOptions` from `biostatviz.io`.
- Produces:
  - `InspectionSeverity` enum.
  - `InspectionIssue`.
  - `SheetSummary`.
  - `InspectionReport`.
  - `InspectionError` and `InspectionReadError`.

- [ ] **Step 1: Write failing contract tests**

Create `tests/unit/inspection/test_models.py`:

```python
from pathlib import Path

from biostatviz.inspection import (
    InspectionIssue,
    InspectionReport,
    InspectionSeverity,
)


def test_action_required_drives_requires_user_input():
    report = InspectionReport(
        source_path=Path("data.csv"),
        source_format="csv",
        issues=(
            InspectionIssue(
                code="POSSIBLE_HEADER_OFFSET",
                severity=InspectionSeverity.ACTION_REQUIRED,
                message="A later row may be the header.",
                candidates=("row:1",),
            ),
        ),
    )

    assert report.requires_user_input is True
    assert report.has_warnings is False


def test_warning_does_not_require_user_input():
    report = InspectionReport(
        source_path=Path("data.csv"),
        source_format="csv",
        issues=(
            InspectionIssue(
                code="MIXED_NUMERIC_TEXT",
                severity=InspectionSeverity.WARNING,
                message="Mixed values detected.",
            ),
        ),
    )

    assert report.requires_user_input is False
    assert report.has_warnings is True
```

- [ ] **Step 2: Run and verify RED**

```powershell
uv run pytest tests/unit/inspection/test_models.py -v
```

Expected: import failure because `biostatviz.inspection` does not exist.

- [ ] **Step 3: Implement `InspectionSeverity` and immutable report models**

Use these exact public fields in `models.py`:

```python
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal

from biostatviz.io import LoadingOptions


class InspectionSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ACTION_REQUIRED = "ACTION_REQUIRED"


@dataclass(frozen=True, slots=True)
class InspectionIssue:
    code: str
    severity: InspectionSeverity
    message: str
    location: str | None = None
    observed: tuple[str, ...] = ()
    candidates: tuple[str, ...] = ()
    suggested_action: str | None = None


@dataclass(frozen=True, slots=True)
class SheetSummary:
    name: str
    non_empty_rows: int
    max_columns: int
    plausible_table: bool


@dataclass(frozen=True, slots=True)
class InspectionReport:
    source_path: Path
    source_format: Literal["csv", "xlsx"]
    sheets: tuple[SheetSummary, ...] = ()
    inspected_sheet: str | int | None = None
    shape_preview: tuple[int, int] = (0, 0)
    issues: tuple[InspectionIssue, ...] = ()
    candidate_loading_options: tuple[LoadingOptions, ...] = ()

    @property
    def requires_user_input(self) -> bool:
        return any(
            issue.severity is InspectionSeverity.ACTION_REQUIRED
            for issue in self.issues
        )

    @property
    def has_warnings(self) -> bool:
        return any(
            issue.severity is InspectionSeverity.WARNING
            for issue in self.issues
        )
```

- [ ] **Step 4: Implement typed inspection exceptions**

`errors.py`:

```python
from biostatviz.io import BioStatVizIOError


class InspectionError(BioStatVizIOError):
    """Base class for failures that prevent inspection."""


class InspectionReadError(InspectionError):
    """Raised when a supported file cannot be previewed for inspection."""
```

Detected ambiguity is never represented by these exceptions; it is an `InspectionIssue`.

- [ ] **Step 5: Export the public contract**

Export all five public types from `biostatviz.inspection`.

- [ ] **Step 6: Run tests**

```powershell
uv run pytest tests/unit/inspection/test_models.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/biostatviz/inspection tests/unit/inspection/test_models.py
git commit -m "feat: define inspection report contracts"
```

---

### Task 3: Read bounded raw CSV/XLSX previews before pandas coercion

**Files:**
- Create: `src/biostatviz/inspection/preview.py`
- Create: `tests/unit/inspection/test_preview_csv.py`
- Create: `tests/unit/inspection/test_preview_xlsx.py`

**Interfaces:**
- Consumes: file `Path`, optional delimiter/encoding/sheet selection.
- Produces internal immutable models:
  - `TablePreview(rows, delimiter, delimiter_candidates, sheet_name)`.
  - `WorkbookPreview(sheets)` where each sheet contains a `TablePreview` and a `SheetSummary`.
  - `read_csv_preview(...)` and `read_xlsx_preview(...)`.

- [ ] **Step 1: Write failing CSV raw-token test**

```python
from pathlib import Path

from biostatviz.inspection.preview import read_csv_preview


def test_csv_preview_preserves_raw_na_tokens(tmp_path: Path):
    path = tmp_path / "raw.csv"
    path.write_text("sample,value\nS1,NA\nS2,N/A\n", encoding="utf-8")

    preview = read_csv_preview(path, encoding="utf-8-sig", delimiter=",", max_rows=10)

    assert preview.rows[1] == ("S1", "NA")
    assert preview.rows[2] == ("S2", "N/A")
```

- [ ] **Step 2: Run and verify RED**

```powershell
uv run pytest tests/unit/inspection/test_preview_csv.py::test_csv_preview_preserves_raw_na_tokens -v
```

Expected: import failure.

- [ ] **Step 3: Implement `TablePreview` and CSV preview reading with stdlib `csv`**

Use the standard library, not pandas, for preview parsing.

```python
@dataclass(frozen=True, slots=True)
class TablePreview:
    rows: tuple[tuple[object, ...], ...]
    delimiter: str | None = None
    delimiter_candidates: tuple[str, ...] = ()
    sheet_name: str | None = None
```

Implement:

```python
def read_csv_preview(
    path: Path,
    *,
    encoding: str = "utf-8-sig",
    delimiter: str | None = None,
    max_rows: int = 50,
) -> TablePreview:
```

If `delimiter` is explicit, parse with it directly.

If absent, score only these candidates in this fixed order:

```python
DELIMITER_CANDIDATES = (",", "\t", ";", "|")
```

A candidate is plausible when, across nonblank preview lines:

- at least two parsed columns occur;
- at least 80% of parsed nonblank rows have the same width.

If exactly one candidate is plausible, use it.
If multiple candidates are plausible, preserve all tied candidates in `delimiter_candidates` and leave `delimiter=None`.
If none is plausible, treat the file as a one-column table and set `delimiter=","` with no ambiguity issue at this low-level reader.

- [ ] **Step 4: Add delimiter detection tests**

```python
def test_csv_preview_detects_semicolon_delimiter(tmp_path: Path):
    path = tmp_path / "data.csv"
    path.write_text("sample;value\nS1;1\nS2;2\n", encoding="utf-8")

    preview = read_csv_preview(path, max_rows=10)

    assert preview.delimiter == ";"
    assert preview.delimiter_candidates == (";",)
```

Also create a synthetic ambiguous case and assert `delimiter is None` plus two candidates.

- [ ] **Step 5: Write failing XLSX raw preview test**

```python
import openpyxl

from biostatviz.inspection.preview import read_xlsx_preview


def test_xlsx_preview_preserves_sheet_names_and_raw_values(tmp_path: Path):
    path = tmp_path / "book.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Raw"
    ws.append(["sample", "value"])
    ws.append(["S1", "NA"])
    wb.create_sheet("Notes").append(["free text"])
    wb.save(path)

    preview = read_xlsx_preview(path, max_rows=20, max_columns=20)

    assert tuple(sheet.summary.name for sheet in preview.sheets) == ("Raw", "Notes")
    assert preview.sheets[0].table.rows[1] == ("S1", "NA")
```

- [ ] **Step 6: Implement bounded XLSX preview with openpyxl**

Use:

```python
openpyxl.load_workbook(path, read_only=True, data_only=False)
```

Do not use pandas in this reader.

For each worksheet read at most `max_rows=50` and `max_columns=50` values. Build `SheetSummary` from observed raw cells. Define `plausible_table=True` when the bounded preview has at least 2 non-empty rows and at least 2 columns containing at least one non-empty value.

- [ ] **Step 7: Wrap decoding/workbook failures in `InspectionReadError`**

CSV `UnicodeDecodeError`, `csv.Error`, and XLSX/openpyxl read failures must become `InspectionReadError` with the source path included.

- [ ] **Step 8: Run preview tests**

```powershell
uv run pytest tests/unit/inspection/test_preview_csv.py tests/unit/inspection/test_preview_xlsx.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add src/biostatviz/inspection/preview.py tests/unit/inspection/test_preview_csv.py tests/unit/inspection/test_preview_xlsx.py
git commit -m "feat: add raw table preview readers"
```

---

### Task 4: Implement deterministic structural checks

**Files:**
- Create: `src/biostatviz/inspection/checks.py`
- Create: `tests/unit/inspection/test_structural_checks.py`

**Interfaces:**
- Consumes: `TablePreview` raw rows.
- Produces `StructuralAnalysis(header_row, shape_preview, issues, candidate_loading_options)`.
- Pure functions only; no file IO and no interaction.

- [ ] **Step 1: Write failing header-offset test**

```python
from biostatviz.inspection import InspectionSeverity
from biostatviz.inspection.checks import inspect_structure
from biostatviz.inspection.preview import TablePreview


def test_metadata_prefix_produces_header_action_required():
    preview = TablePreview(
        rows=(
            ("Experiment: GFP screen", "", ""),
            ("Date: 2026-08-16", "", ""),
            ("sample", "group", "gfp"),
            ("WT1", "WT", "101"),
            ("KO1", "KO", "145"),
        ),
        delimiter=",",
        delimiter_candidates=(",",),
    )

    result = inspect_structure(preview)

    issue = next(i for i in result.issues if i.code == "POSSIBLE_HEADER_OFFSET")
    assert issue.severity is InspectionSeverity.ACTION_REQUIRED
    assert issue.candidates == ("row:2",)
```

- [ ] **Step 2: Run and verify RED**

```powershell
uv run pytest tests/unit/inspection/test_structural_checks.py::test_metadata_prefix_produces_header_action_required -v
```

- [ ] **Step 3: Implement bounded header scoring**

Inspect at most the first 10 rows. Normalize a cell as blank when it is `None` or a string whose `.strip()` is empty.

For each candidate row compute:

```text
non_empty_count
unique_non_empty_count
text_count
following_rectangular_rows
```

A plausible header requires:

```text
non_empty_count >= 2
unique_non_empty_count == non_empty_count
text_count / non_empty_count >= 0.5
at least one of the next 3 nonblank rows has >= 2 nonblank cells
```

Choose the earliest highest-scoring row, where score is:

```text
non_empty_count
+ 2 if all labels are unique
+ 2 if text ratio >= 0.5
+ min(following_rectangular_rows, 3)
```

Behavior:

- if row 0 is the sole best plausible candidate: no header issue;
- if a later row is the sole best plausible candidate: `POSSIBLE_HEADER_OFFSET`, `ACTION_REQUIRED`;
- if multiple rows tie for best plausible candidate: `HEADER_ROW_AMBIGUOUS`, `ACTION_REQUIRED` with every candidate;
- if no row is plausible: `HEADER_NOT_DETERMINED`, `ACTION_REQUIRED`.

- [ ] **Step 4: Detect duplicate labels from raw header cells**

Test:

```python
def test_duplicate_raw_column_labels_are_action_required():
    preview = TablePreview(
        rows=(
            ("sample", "value", "value"),
            ("S1", "1", "2"),
        ),
        delimiter=",",
        delimiter_candidates=(",",),
    )

    result = inspect_structure(preview)

    issue = next(i for i in result.issues if i.code == "DUPLICATE_COLUMN_NAMES")
    assert issue.severity is InspectionSeverity.ACTION_REQUIRED
    assert "value" in issue.observed
```

Do not read columns through pandas, because pandas may already mangle duplicates.

- [ ] **Step 5: Detect blank internal rows and columns**

Implement `BLANK_ROW` and `BLANK_COLUMN` issues using the apparent table region beginning at the selected candidate header row.

- Fully blank internal row: `INFO` if exactly one, `WARNING` if more than 10% of preview data rows are blank.
- Fully blank internal column: `WARNING`.
- Leading blank rows before a later header contribute only to the header-offset issue; do not duplicate them as internal blank-row issues.

- [ ] **Step 6: Produce candidate `LoadingOptions` for deterministic alternatives**

For a unique later header row, include:

```python
LoadingOptions(header=<zero_based_row>, delimiter=preview.delimiter or ",")
```

For tied header candidates, return one `LoadingOptions` per row.

Do not create a candidate when delimiter ambiguity is unresolved.

- [ ] **Step 7: Run structural tests**

```powershell
uv run pytest tests/unit/inspection/test_structural_checks.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add src/biostatviz/inspection/checks.py tests/unit/inspection/test_structural_checks.py
git commit -m "feat: add structural table checks"
```

---

### Task 5: Add basic data-quality checks without semantic cleaning

**Files:**
- Modify: `src/biostatviz/inspection/checks.py`
- Create: `tests/unit/inspection/test_quality_checks.py`

**Interfaces:**
- Consumes: raw `TablePreview` plus selected/assumed header row.
- Produces structured `INFO`/`WARNING` issues only; these checks never create cleaned values.

- [ ] **Step 1: Write failing placeholder-token warning test**

```python
from biostatviz.inspection.checks import inspect_quality
from biostatviz.inspection.preview import TablePreview


def test_placeholder_token_inside_numeric_column_is_reported_verbatim():
    preview = TablePreview(
        rows=(
            ("sample", "intensity"),
            ("S1", "10.1"),
            ("S2", "ND"),
            ("S3", "12.5"),
        ),
        delimiter=",",
        delimiter_candidates=(",",),
    )

    issues = inspect_quality(preview, header_row=0)

    issue = next(i for i in issues if i.code == "PLACEHOLDER_TOKEN_IN_NUMERIC_COLUMN")
    assert issue.observed == ("ND",)
    assert issue.location == "column:intensity"
```

- [ ] **Step 2: Run and verify RED**

```powershell
uv run pytest tests/unit/inspection/test_quality_checks.py::test_placeholder_token_inside_numeric_column_is_reported_verbatim -v
```

- [ ] **Step 3: Implement conservative numeric/text classification**

Helpers:

```python
PLACEHOLDER_TOKENS = {"nd", "na", "n/a", "-"}


def _is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _is_numeric_like(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return False
        try:
            float(text)
        except ValueError:
            return False
        return True
    return False
```

A column is numeric-looking when it has at least 2 numeric-like nonblank values and numeric-like values are at least 60% of nonblank observed values.

If the unexpected text values are all placeholder tokens, emit `PLACEHOLDER_TOKEN_IN_NUMERIC_COLUMN` (`WARNING`). Otherwise emit `MIXED_NUMERIC_TEXT` (`WARNING`).

Include counts in `message` and representative unexpected raw tokens in `observed`.

- [ ] **Step 4: Add blank-value reporting without imputation**

Test a column containing actual blank cells and assert an `INFO` issue with code `BLANK_VALUES_PRESENT` and the count in `observed`, while the raw preview stays unchanged.

- [ ] **Step 5: Implement conservative duplicate-identifier detection**

Only inspect columns whose normalized header is one of:

```python
IDENTIFIER_HEADERS = {
    "sample",
    "sample_id",
    "sample id",
    "id",
    "name",
    "sample_name",
    "sample name",
}
```

If repeated nonblank values occur, emit:

```text
code=POSSIBLE_DUPLICATE_IDENTIFIER
severity=WARNING
```

Do not check arbitrary numeric/measurement columns for duplicate-sample semantics.

- [ ] **Step 6: Add regression test preventing false duplicate-sample warnings on repeated measurements**

```python
def test_repeated_measurement_values_are_not_called_duplicate_identifiers():
    preview = TablePreview(
        rows=(
            ("group", "value"),
            ("WT", "1.0"),
            ("KO", "1.0"),
        ),
        delimiter=",",
        delimiter_candidates=(",",),
    )

    issues = inspect_quality(preview, header_row=0)

    assert not any(i.code == "POSSIBLE_DUPLICATE_IDENTIFIER" for i in issues)
```

- [ ] **Step 7: Run quality tests**

```powershell
uv run pytest tests/unit/inspection/test_quality_checks.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add src/biostatviz/inspection/checks.py tests/unit/inspection/test_quality_checks.py
git commit -m "feat: add basic table quality checks"
```

---

### Task 6: Implement `inspect_table()` orchestration and worksheet/delimiter ambiguity

**Files:**
- Create: `src/biostatviz/inspection/inspector.py`
- Modify: `src/biostatviz/inspection/__init__.py`
- Create: `tests/unit/inspection/test_inspector.py`

**Interfaces:**
- Consumes: path, optional `sheet_name`, `encoding`, `delimiter`, bounded preview limits.
- Produces:

```python
def inspect_table(
    path: str | Path,
    sheet_name: str | int | None = None,
    *,
    encoding: str = "utf-8-sig",
    delimiter: str | None = None,
    max_rows: int = 50,
    max_columns: int = 50,
) -> InspectionReport:
```

No `safe_fixes` parameter exists.

- [ ] **Step 1: Write failing clean-CSV acceptance test**

```python
from biostatviz.inspection import inspect_table


def test_clean_csv_has_no_blocking_issues(tmp_path):
    path = tmp_path / "clean.csv"
    path.write_text("sample,value\nS1,1\nS2,2\n", encoding="utf-8")

    report = inspect_table(path)

    assert report.source_format == "csv"
    assert report.shape_preview == (3, 2)
    assert report.requires_user_input is False
```

- [ ] **Step 2: Run and verify RED**

```powershell
uv run pytest tests/unit/inspection/test_inspector.py::test_clean_csv_has_no_blocking_issues -v
```

- [ ] **Step 3: Implement common path/format validation**

Reuse `TableNotFoundError` and `UnsupportedTableFormatError` from Module 01. Only `.csv` and `.xlsx` proceed.

- [ ] **Step 4: Assemble CSV reports**

Rules:

- read raw preview;
- if `delimiter_candidates` contains more than one candidate while `delimiter is None`, append:

```text
code=DELIMITER_AMBIGUOUS
severity=ACTION_REQUIRED
candidates=(candidate strings)
```

and do not run structural/quality checks that depend on a resolved delimiter;
- otherwise run `inspect_structure()` then `inspect_quality()`;
- merge issues in deterministic order: format-level issues, structural issues, quality issues;
- deduplicate candidate `LoadingOptions` by value while preserving order.

- [ ] **Step 5: Write worksheet ambiguity tests**

Create a workbook where `Raw` and `Summary` both have >=2 rows and >=2 nonempty columns, and `Notes` contains one free-text cell.

Assert:

```python
issue = next(i for i in report.issues if i.code == "MULTIPLE_PLAUSIBLE_SHEETS")
assert issue.severity is InspectionSeverity.ACTION_REQUIRED
assert issue.candidates == ("Raw", "Summary")
assert report.inspected_sheet is None
```

- [ ] **Step 6: Implement XLSX sheet-selection rules**

If `sheet_name` is explicit:

- inspect only that sheet;
- if missing, raise existing `ExcelSheetNotFoundError`;
- preserve all sheet summaries in `report.sheets`.

If no sheet is explicit:

- one workbook sheet: inspect it;
- multiple sheets with exactly one `plausible_table=True`: inspect that sheet and do not require input merely because note-like sheets exist;
- two or more plausible sheets: emit `MULTIPLE_PLAUSIBLE_SHEETS` `ACTION_REQUIRED`, set `inspected_sheet=None`, and include one `LoadingOptions(sheet_name=<candidate>)` per candidate;
- no plausible sheet: emit `NO_PLAUSIBLE_TABLE_SHEET` `ACTION_REQUIRED` with all sheet names as candidates.

Do not arbitrarily inspect one plausible candidate when multiple candidates exist.

- [ ] **Step 7: Add source-file immutability test**

Hash the file bytes before and after `inspect_table()` and assert equality.

- [ ] **Step 8: Export `inspect_table`**

Add it to `biostatviz.inspection.__all__`.

- [ ] **Step 9: Run all inspection-core tests**

```powershell
uv run pytest tests/unit/inspection/test_models.py tests/unit/inspection/test_preview_csv.py tests/unit/inspection/test_preview_xlsx.py tests/unit/inspection/test_structural_checks.py tests/unit/inspection/test_quality_checks.py tests/unit/inspection/test_inspector.py -v
```

Expected: PASS.

- [ ] **Step 10: Commit**

```powershell
git add src/biostatviz/inspection tests/unit/inspection/test_inspector.py
git commit -m "feat: add deterministic table inspection"
```

---

### Task 7: Add Agent and CLI adapters that consume the same report

**Files:**
- Create: `src/biostatviz/inspection/agent.py`
- Create: `src/biostatviz/inspection/cli.py`
- Create: `tests/unit/inspection/test_adapters.py`

**Interfaces:**
- Consumes: `InspectionReport` only.
- Produces:
  - `build_agent_questions(report) -> tuple[str, ...]`.
  - `format_cli_report(report) -> str`.
  - `resolve_cli_loading_options(report, *, input_fn=input) -> LoadingOptions | None` for simple supported `ACTION_REQUIRED` choices.

- [ ] **Step 1: Write failing Agent adapter test**

```python
from pathlib import Path

from biostatviz.inspection import InspectionIssue, InspectionReport, InspectionSeverity
from biostatviz.inspection.agent import build_agent_questions


def test_agent_questions_are_built_only_from_action_required_issues():
    report = InspectionReport(
        source_path=Path("book.xlsx"),
        source_format="xlsx",
        issues=(
            InspectionIssue(
                code="MULTIPLE_PLAUSIBLE_SHEETS",
                severity=InspectionSeverity.ACTION_REQUIRED,
                message="Multiple plausible worksheets detected.",
                candidates=("Raw", "Summary"),
            ),
            InspectionIssue(
                code="BLANK_VALUES_PRESENT",
                severity=InspectionSeverity.INFO,
                message="Two blanks detected.",
            ),
        ),
    )

    questions = build_agent_questions(report)

    assert len(questions) == 1
    assert "Raw" in questions[0]
    assert "Summary" in questions[0]
```

- [ ] **Step 2: Implement stable question rendering**

Support at least:

- `MULTIPLE_PLAUSIBLE_SHEETS` -> ask which sheet;
- `POSSIBLE_HEADER_OFFSET` / `HEADER_ROW_AMBIGUOUS` -> ask which header row;
- `DELIMITER_AMBIGUOUS` -> ask which delimiter.

Unknown future `ACTION_REQUIRED` issues fall back to:

```text
<message> Candidates: <comma-separated candidates>. Please choose explicitly.
```

The Agent adapter returns strings only and makes no choice.

- [ ] **Step 3: Write failing CLI rendering test**

Assert output contains severity, issue message, and numbered candidates but does not alter the report.

- [ ] **Step 4: Implement `format_cli_report()`**

Render every issue in order:

```text
[INFO] ...
[WARNING] ...
[ACTION REQUIRED] ...
```

Use numbered candidate lines only when candidates exist.

- [ ] **Step 5: Implement the opt-in CLI resolver**

`resolve_cli_loading_options()` may call the supplied `input_fn`. It supports one unambiguous choice family at a time:

- sheet issue -> return `LoadingOptions(sheet_name=<selected>)`;
- header issue -> return `LoadingOptions(header=<selected row>)`;
- delimiter issue -> return `LoadingOptions(delimiter=<selected>)`.

If there are zero `ACTION_REQUIRED` issues, return `None`.
If there are multiple unrelated action-required issue families, do not guess how to merge them; raise `ValueError("Multiple independent decisions require orchestration.")`. Later orchestration can combine them explicitly.

- [ ] **Step 6: Prove the core contains no interaction dependency**

Add a source-level test that imports `inspect_table`, runs it while monkeypatching `builtins.input` to raise, and confirms inspection still succeeds.

Also assert `"openai"`, `"anthropic"`, and `"mcp"` are not imported anywhere under `src/biostatviz/inspection/` core files `models.py`, `preview.py`, `checks.py`, and `inspector.py`.

- [ ] **Step 7: Run adapter tests**

```powershell
uv run pytest tests/unit/inspection/test_adapters.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add src/biostatviz/inspection/agent.py src/biostatviz/inspection/cli.py tests/unit/inspection/test_adapters.py
git commit -m "feat: add inspection interaction adapters"
```

---

### Task 8: End-to-end acceptance, README usage, and Module 01.5 exit gate

**Files:**
- Modify: `README.md`
- Create: `tests/unit/inspection/test_acceptance.py`

**Interfaces:**
- Consumes: public `inspect_table()`, `LoadingOptions`, `load_table()`.
- Produces: acceptance guarantee for the complete `inspect -> user decision -> load` workflow.

- [ ] **Step 1: Write an acceptance test for leading metadata rows**

```python
from biostatviz.inspection import inspect_table
from biostatviz.io import load_table


def test_inspect_then_explicit_load_preserves_scientific_tokens(tmp_path):
    path = tmp_path / "experiment.csv"
    path.write_text(
        "Experiment: GFP screen,,\n"
        "sample,group,intensity\n"
        "WT1,WT,101\n"
        "WT2,WT,NA\n"
        "KO1,KO,145\n",
        encoding="utf-8",
    )

    report = inspect_table(path)

    assert report.requires_user_input is True
    header_option = next(
        option for option in report.candidate_loading_options if option.header == 1
    )

    loaded = load_table(path, options=header_option)

    assert loaded.data.columns.tolist() == ["sample", "group", "intensity"]
    assert loaded.data["intensity"].tolist() == ["101", "NA", "145"]
```

- [ ] **Step 2: Add XLSX multi-sheet acceptance test**

Verify inspection returns sheet candidates, the test simulates selecting `Raw`, then `load_table(..., options=LoadingOptions(sheet_name="Raw"))` loads only that sheet.

- [ ] **Step 3: Run full test suite**

```powershell
uv run pytest -v
```

Expected: all tests PASS with no collection errors.

- [ ] **Step 4: Run manual smoke tests**

Clean CSV:

```powershell
uv run python -c "from biostatviz.inspection import inspect_table; r=inspect_table('examples/data/two_group_gfp.csv'); print(r.requires_user_input, r.issues)"
```

Expected: `False` and no blocking structural issue.

Module 01 regression:

```powershell
uv run python -c "from biostatviz.io import load_table; x=load_table('examples/data/two_group_gfp.csv'); print(x.data.shape, x.source_format)"
```

Expected:

```text
(6, 3) csv
```

- [ ] **Step 5: Document the public workflow in README**

Add:

```markdown
## Inspect imperfect tables before loading

```python
from biostatviz.inspection import inspect_table
from biostatviz.io import load_table

report = inspect_table("experiment.csv")

if report.requires_user_input:
    print(report.issues)
else:
    loaded = load_table("experiment.csv")
```

BioStatViz inspection reports structural ambiguity and basic data-quality risks without silently cleaning the file. Agent and CLI integrations consume the same structured `InspectionReport`. Ambiguous choices such as worksheet, header row, or delimiter must be supplied explicitly before final loading.
```

- [ ] **Step 6: Verify the design acceptance criteria line by line**

Confirm with tests/evidence:

1. Clean CSV/XLSX deterministic inspection.
2. Structured imperfect-table issues.
3. All three severities covered.
4. No silent ambiguity resolution.
5. Placeholder and mixed text not silently coerced.
6. Core has no interaction/LLM dependency.
7. Agent and CLI consume one `InspectionReport` contract.
8. Inspection changes no source bytes.
9. Existing Module 01 tests remain green.
10. No Module 02 statistical profiling behavior exists.

- [ ] **Step 7: Commit**

```powershell
git add README.md tests/unit/inspection/test_acceptance.py
git commit -m "test: validate table inspection workflow"
```

---

## Module 01.5 Exit Gate

Do not begin Module 02 until all of the following pass:

```powershell
uv run pytest -v
uv run python -c "from biostatviz.inspection import inspect_table; r=inspect_table('examples/data/two_group_gfp.csv'); print(r.requires_user_input)"
uv run python -c "from biostatviz.io import load_table; x=load_table('examples/data/two_group_gfp.csv'); print(x.data.shape)"
```

Required results:

```text
pytest: all tests PASS
example inspection requires_user_input: False
example shape: (6, 3)
```

Manual review checklist:

- Raw CSV/XLSX previews are read before pandas default NA coercion.
- `NA`, `N/A`, `ND`, and `-` remain observable as user-authored tokens.
- `inspect_table()` has no `safe_fixes` parameter and performs no mutation.
- Multiple plausible sheets never trigger automatic sheet selection.
- Later/ambiguous header candidates require an explicit user choice.
- Duplicate raw column labels are detected before pandas mangling.
- Mixed numeric/text warnings never coerce values.
- Duplicate sample warnings are limited to conservative identifier-like columns.
- Agent adapter asks; it never chooses.
- CLI interaction is isolated to `inspection/cli.py`.
- `LoadingOptions` carries explicit user decisions to Module 01.
- Existing `load_table(path)` and `load_table(path, sheet_name=...)` callers still work.
- No statistical profiling, outlier detection, experimental-design inference, or data cleaning is introduced.
