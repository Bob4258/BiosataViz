# BioStatViz Module 01.5: Table Inspection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic structural-inspection and basic data-quality layer for imperfect scientific CSV/XLSX files, shared by Agent/MCP and CLI workflows, without silently changing scientific meaning.

**Architecture:** Module 01 remains the deterministic final loader. A new `biostatviz.inspection` package reads bounded raw previews with the standard-library `csv` module and openpyxl before pandas can coerce user-authored tokens, runs pure structural/quality checks, and returns one structured `InspectionReport`. Agent and CLI adapters consume that same report; user decisions become immutable `LoadingOptions` that are explicitly passed back to Module 01.

**Tech Stack:** Python 3.11, uv, pandas >=2.2,<3.0, openpyxl >=3.1,<4.0, Python standard-library `csv`, pytest >=8,<9, Git.

## Global Constraints

- Primary local OS: Windows.
- Python version: 3.11.
- Package/environment manager: uv.
- Testing framework: pytest.
- Version control: Git.
- Supported formats remain `.csv` and `.xlsx` only.
- Inspection never writes to or modifies the source file.
- Raw inspection occurs before pandas default NA/type coercion.
- `inspect_table()` is deterministic and non-interactive.
- Inspection core files contain no `input()`, terminal UI, MCP transport, LLM calls, or arbitrary Python execution.
- Severity values are exactly `INFO`, `WARNING`, and `ACTION_REQUIRED`.
- Any unresolved `ACTION_REQUIRED` issue means BioStatViz must not choose that interpretation for the user.
- No automatic data cleaning is implemented.
- `ND`, `NA`, `N/A`, `-`, and similar observed values are reported as raw tokens, never assigned biological meaning.
- No control/treatment inference, replicate inference, statistical-test selection, outlier removal, imputation, normalization, scaling, batch correction, or Dataset Profiling is implemented.
- Module 02 remains responsible for statistical Dataset Profiling.
- Implementation follows strict red-green-refactor TDD.
- Existing Module 01 calls `load_table(path)` and `load_table(path, sheet_name=...)` remain supported.
- Existing Module 01 tests must remain green after every task touching IO.

---

## Final File Structure

```text
src/biostatviz/
├── io/
│   ├── __init__.py
│   ├── errors.py
│   ├── loader.py
│   └── models.py
└── inspection/
    ├── __init__.py
    ├── errors.py
    ├── models.py
    ├── preview.py
    ├── checks.py
    ├── inspector.py
    ├── agent.py
    └── cli.py

tests/unit/
├── io/
│   ├── test_csv_loader.py
│   ├── test_excel_loader.py
│   ├── test_loader_errors.py
│   └── test_loading_options.py
└── inspection/
    ├── test_models.py
    ├── test_preview_csv.py
    ├── test_preview_xlsx.py
    ├── test_structural_checks.py
    ├── test_quality_checks.py
    ├── test_inspector.py
    ├── test_adapters.py
    └── test_acceptance.py
```

Dependency direction is one-way:

```text
inspection.models -> io.LoadingOptions
inspection.preview -> inspection.models/errors
inspection.checks -> inspection.models + io.LoadingOptions
inspection.inspector -> preview + checks
inspection.agent/cli -> InspectionReport
io -> never imports inspection
```

---

### Task 1: Add explicit Module 01 loading options and stop default NA-token coercion

**Files:**
- Modify: `src/biostatviz/io/models.py`
- Modify: `src/biostatviz/io/loader.py`
- Modify: `src/biostatviz/io/__init__.py`
- Modify: `tests/unit/io/test_csv_loader.py`
- Create: `tests/unit/io/test_loading_options.py`

**Interfaces:**
- Produces `LoadingOptions`:

```python
@dataclass(frozen=True, slots=True)
class LoadingOptions:
    sheet_name: str | int | None = None
    header: int | None = 0
    delimiter: str = ","
    encoding: str = "utf-8-sig"
    keep_default_na: bool = False
```

- Produces backward-compatible loader:

```python
def load_table(
    path: str | Path,
    sheet_name: str | int | None = None,
    *,
    options: LoadingOptions | None = None,
) -> LoadedTable:
```

- [ ] **Step 1: Write a failing default-token-preservation test**

`tests/unit/io/test_loading_options.py`:

```python
from pathlib import Path

import pandas as pd
import pytest

from biostatviz.io import LoadingOptions, TableReadError, load_table


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

Update the existing CSV preservation test expected value to:

```python
expected = pd.read_csv(csv_path, keep_default_na=False)
```

- [ ] **Step 2: Verify RED**

```powershell
uv run pytest tests/unit/io/test_loading_options.py::test_csv_preserves_user_authored_na_like_tokens_by_default -v
```

Expected: FAIL because pandas currently converts `NA`/`N/A` using its default NA table.

- [ ] **Step 3: Implement `LoadingOptions` and export it from `biostatviz.io`**

Add the dataclass above to `io/models.py`, import it in `io/__init__.py`, and add `"LoadingOptions"` to `__all__`.

- [ ] **Step 4: Resolve legacy arguments into one immutable options object**

At the start of `load_table()` after path validation:

```python
if options is not None and sheet_name is not None:
    raise TableReadError(
        "Pass Excel sheet selection either with sheet_name or LoadingOptions, not both."
    )

resolved = options or LoadingOptions(sheet_name=sheet_name)
```

For CSV:

```python
if resolved.sheet_name is not None:
    raise TableReadError("sheet_name is only valid for .xlsx files.")

data = pd.read_csv(
    source_path,
    sep=resolved.delimiter,
    encoding=resolved.encoding,
    header=resolved.header,
    keep_default_na=resolved.keep_default_na,
)
```

For XLSX:

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

Continue wrapping missing-sheet `ValueError` as `ExcelSheetNotFoundError` and other read failures as `TableReadError`.

- [ ] **Step 5: Test explicit delimiter and header decisions**

```python
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

Also test the conflict path:

```python
def test_load_table_rejects_duplicate_sheet_configuration(tmp_path: Path):
    path = tmp_path / "book.xlsx"
    pd.DataFrame({"x": [1]}).to_excel(path, index=False, engine="openpyxl")

    with pytest.raises(TableReadError, match="either with sheet_name or LoadingOptions"):
        load_table(
            path,
            sheet_name="Sheet1",
            options=LoadingOptions(sheet_name="Sheet1"),
        )
```

- [ ] **Step 6: Run all IO tests**

```powershell
uv run pytest tests/unit/io -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/biostatviz/io tests/unit/io
git commit -m "feat: add explicit table loading options"
```

---

### Task 2: Define immutable inspection contracts and typed inspection failures

**Files:**
- Create: `src/biostatviz/inspection/__init__.py`
- Create: `src/biostatviz/inspection/errors.py`
- Create: `src/biostatviz/inspection/models.py`
- Create: `tests/unit/inspection/test_models.py`

**Interfaces:**
- Produces exactly these public model types: `InspectionSeverity`, `InspectionIssue`, `SheetSummary`, `InspectionReport`.
- Produces exactly these public exception types: `InspectionError`, `InspectionReadError`.

- [ ] **Step 1: Write failing model tests**

```python
from pathlib import Path

from biostatviz.inspection import (
    InspectionIssue,
    InspectionReport,
    InspectionSeverity,
)


def test_action_required_sets_requires_user_input():
    report = InspectionReport(
        source_path=Path("data.csv"),
        source_format="csv",
        issues=(
            InspectionIssue(
                code="POSSIBLE_HEADER_OFFSET",
                severity=InspectionSeverity.ACTION_REQUIRED,
                message="A later row may be the header.",
                candidates=("row:2",),
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

- [ ] **Step 2: Verify RED**

```powershell
uv run pytest tests/unit/inspection/test_models.py -v
```

Expected: import failure because the package does not yet exist.

- [ ] **Step 3: Implement the model contract**

`inspection/models.py`:

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

- [ ] **Step 4: Implement typed failures**

`inspection/errors.py`:

```python
from biostatviz.io import BioStatVizIOError


class InspectionError(BioStatVizIOError):
    """Base class for failures that prevent inspection."""


class InspectionReadError(InspectionError):
    """Raised when a supported file cannot be previewed for inspection."""
```

Ambiguity is not an exception; it is an `InspectionIssue`.

- [ ] **Step 5: Export all six public types**

`inspection/__init__.py` must export the four models and two exceptions above.

- [ ] **Step 6: Verify GREEN and commit**

```powershell
uv run pytest tests/unit/inspection/test_models.py -v
git add src/biostatviz/inspection tests/unit/inspection/test_models.py
git commit -m "feat: define inspection report contracts"
```

---

### Task 3: Build bounded raw CSV/XLSX preview readers

**Files:**
- Create: `src/biostatviz/inspection/preview.py`
- Create: `tests/unit/inspection/test_preview_csv.py`
- Create: `tests/unit/inspection/test_preview_xlsx.py`

**Interfaces:**
- Internal immutable types:

```python
@dataclass(frozen=True, slots=True)
class TablePreview:
    rows: tuple[tuple[object, ...], ...]
    delimiter: str | None = None
    delimiter_candidates: tuple[str, ...] = ()
    sheet_name: str | None = None


@dataclass(frozen=True, slots=True)
class SheetPreview:
    summary: SheetSummary
    table: TablePreview


@dataclass(frozen=True, slots=True)
class WorkbookPreview:
    sheets: tuple[SheetPreview, ...]
```

- Reader APIs:

```python
def read_csv_preview(
    path: Path,
    *,
    encoding: str = "utf-8-sig",
    delimiter: str | None = None,
    max_rows: int = 50,
) -> TablePreview:
    ...


def read_xlsx_preview(
    path: Path,
    *,
    max_rows: int = 50,
    max_columns: int = 50,
) -> WorkbookPreview:
    ...
```

- [ ] **Step 1: Write failing raw-token CSV test**

```python
from pathlib import Path

from biostatviz.inspection.preview import read_csv_preview


def test_csv_preview_preserves_raw_na_tokens(tmp_path: Path):
    path = tmp_path / "raw.csv"
    path.write_text("sample,value\nS1,NA\nS2,N/A\n", encoding="utf-8")

    preview = read_csv_preview(
        path,
        encoding="utf-8-sig",
        delimiter=",",
        max_rows=10,
    )

    assert preview.rows[1] == ("S1", "NA")
    assert preview.rows[2] == ("S2", "N/A")
```

- [ ] **Step 2: Verify RED**

```powershell
uv run pytest tests/unit/inspection/test_preview_csv.py::test_csv_preview_preserves_raw_na_tokens -v
```

- [ ] **Step 3: Implement deterministic CSV delimiter scoring**

Use only:

```python
DELIMITER_CANDIDATES = (",", "\t", ";", "|")
```

Read at most `max_rows` physical rows from text opened with `newline=""`.

For each delimiter parse the same nonblank lines with `csv.reader`. It is plausible when:

```text
maximum parsed width >= 2
modal width count / number of nonblank parsed rows >= 0.80
```

Keep the candidate score as `(consistency_ratio, modal_width)`.

Selection rules:

- explicit delimiter -> use it; `delimiter_candidates=(delimiter,)`;
- one plausible candidate -> use it;
- multiple plausible candidates -> keep only candidates tied for the highest score; if one top score remains, use it; if >1 top scores remain, set `delimiter=None` and preserve tied candidates;
- zero plausible candidates -> parse as a one-column CSV using comma, `delimiter=","`, `delimiter_candidates=()`.

This avoids declaring comma and semicolon simultaneously ambiguous merely because both appear somewhere in free text.

- [ ] **Step 4: Add delimiter tests**

```python
def test_csv_preview_detects_semicolon_delimiter(tmp_path: Path):
    path = tmp_path / "data.csv"
    path.write_text("sample;value\nS1;1\nS2;2\n", encoding="utf-8")

    preview = read_csv_preview(path, max_rows=10)

    assert preview.delimiter == ";"
```

Add one intentionally tied fixture and assert `delimiter is None` plus the tied candidates in deterministic candidate order.

- [ ] **Step 5: Write failing XLSX raw-preview test**

```python
import openpyxl

from biostatviz.inspection.preview import read_xlsx_preview


def test_xlsx_preview_preserves_sheets_and_raw_tokens(tmp_path):
    path = tmp_path / "book.xlsx"
    wb = openpyxl.Workbook()
    raw = wb.active
    raw.title = "Raw"
    raw.append(["sample", "value"])
    raw.append(["S1", "NA"])
    notes = wb.create_sheet("Notes")
    notes.append(["free text"])
    wb.save(path)

    preview = read_xlsx_preview(path, max_rows=20, max_columns=20)

    assert tuple(s.summary.name for s in preview.sheets) == ("Raw", "Notes")
    assert preview.sheets[0].table.rows[1] == ("S1", "NA")
```

- [ ] **Step 6: Implement XLSX preview using openpyxl, not pandas**

Use:

```python
openpyxl.load_workbook(path, read_only=True, data_only=False)
```

For each sheet, read at most `max_rows` x `max_columns` cells. `SheetSummary` values are computed from bounded observed cells:

```text
non_empty_rows = count of rows containing at least one nonblank cell
max_columns = highest 1-based observed column position containing a nonblank cell, else 0
plausible_table = non_empty_rows >= 2 and max_columns >= 2
```

`TablePreview.sheet_name` is the worksheet name.

- [ ] **Step 7: Wrap preview failures**

Convert CSV decoding/`csv.Error` and XLSX/openpyxl read failures to `InspectionReadError` with the source path in the message.

- [ ] **Step 8: Verify preview suite and commit**

```powershell
uv run pytest tests/unit/inspection/test_preview_csv.py tests/unit/inspection/test_preview_xlsx.py -v
git add src/biostatviz/inspection/preview.py tests/unit/inspection/test_preview_csv.py tests/unit/inspection/test_preview_xlsx.py
git commit -m "feat: add raw table preview readers"
```

---

### Task 4: Implement deterministic structural analysis

**Files:**
- Create: `src/biostatviz/inspection/checks.py`
- Create: `tests/unit/inspection/test_structural_checks.py`

**Interfaces:**
- Internal result type:

```python
@dataclass(frozen=True, slots=True)
class StructuralAnalysis:
    header_row: int | None
    shape_preview: tuple[int, int]
    issues: tuple[InspectionIssue, ...]
    candidate_loading_options: tuple[LoadingOptions, ...]
```

- Main API:

```python
def inspect_structure(
    preview: TablePreview,
    *,
    base_options: LoadingOptions,
) -> StructuralAnalysis:
    ...
```

`base_options` is required so header candidates preserve the already known sheet, delimiter, encoding, and NA policy.

- [ ] **Step 1: Write failing metadata-prefix/header-offset test**

```python
from biostatviz.inspection import InspectionSeverity
from biostatviz.inspection.checks import inspect_structure
from biostatviz.inspection.preview import TablePreview
from biostatviz.io import LoadingOptions


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

    result = inspect_structure(
        preview,
        base_options=LoadingOptions(delimiter=","),
    )

    issue = next(i for i in result.issues if i.code == "POSSIBLE_HEADER_OFFSET")
    assert issue.severity is InspectionSeverity.ACTION_REQUIRED
    assert issue.candidates == ("row:2",)
    assert result.candidate_loading_options[0].header == 2
```

- [ ] **Step 2: Verify RED**

```powershell
uv run pytest tests/unit/inspection/test_structural_checks.py::test_metadata_prefix_produces_header_action_required -v
```

- [ ] **Step 3: Implement bounded header scoring that favors label rows over data rows**

Inspect at most the first 10 rows. Blank means `None` or stripped empty string.

A plausible header requires:

```text
non_empty_count >= 2
all nonblank labels unique after str(value).strip().casefold()
text_count / non_empty_count >= 0.5
at least one of the next 3 nonblank rows has >=2 nonblank cells
```

For each plausible row calculate:

```text
score = non_empty_count
      + 2
      + text_count
      + min(following_rectangular_rows, 3)
```

The fixed `+2` is the uniqueness bonus because uniqueness is required. Using `text_count`, rather than only a boolean text-ratio bonus, ensures a true all-text header such as `sample/group/gfp` outranks a mixed text/numeric data row such as `WT1/WT/101` in the canonical fixture.

Behavior:

- row 0 sole best -> no header issue;
- later row sole best -> `POSSIBLE_HEADER_OFFSET`, `ACTION_REQUIRED`;
- tied best rows -> `HEADER_ROW_AMBIGUOUS`, `ACTION_REQUIRED` with candidates in row order;
- no plausible row -> `HEADER_NOT_DETERMINED`, `ACTION_REQUIRED`.

For every header candidate use:

```python
from dataclasses import replace

replace(base_options, header=candidate_row)
```

Never construct a fresh `LoadingOptions` that loses existing sheet/delimiter/encoding choices.

- [ ] **Step 4: Detect raw duplicate column names before pandas mangling**

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

    result = inspect_structure(
        preview,
        base_options=LoadingOptions(delimiter=","),
    )

    issue = next(i for i in result.issues if i.code == "DUPLICATE_COLUMN_NAMES")
    assert issue.severity is InspectionSeverity.ACTION_REQUIRED
    assert issue.observed == ("value",)
```

Normalize only for duplicate comparison; report the original raw label text in `observed`.

- [ ] **Step 5: Detect internal blank rows/columns**

Starting at the selected sole-best header row:

- one fully blank internal data row -> `BLANK_ROW`, `INFO`;
- blank rows >10% of bounded data rows -> one `BLANK_ROW`, `WARNING` with row indices in `observed`;
- fully blank column between first and last nonblank header/data column -> `BLANK_COLUMN`, `WARNING` with 0-based column indices in `observed`.

Leading blank rows before a later header are represented by the header issue, not duplicated as internal blank-row issues.

- [ ] **Step 6: Verify structural suite and commit**

```powershell
uv run pytest tests/unit/inspection/test_structural_checks.py -v
git add src/biostatviz/inspection/checks.py tests/unit/inspection/test_structural_checks.py
git commit -m "feat: add structural table checks"
```

---

### Task 5: Add basic quality checks with raw evidence and no coercion

**Files:**
- Modify: `src/biostatviz/inspection/checks.py`
- Create: `tests/unit/inspection/test_quality_checks.py`

**Interfaces:**

```python
def inspect_quality(
    preview: TablePreview,
    *,
    header_row: int,
) -> tuple[InspectionIssue, ...]:
    ...
```

Quality checks return `INFO`/`WARNING` only and never produce changed values.

- [ ] **Step 1: Write failing placeholder warning test**

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
    assert issue.location == "column:intensity"
    assert issue.observed == ("ND",)
```

- [ ] **Step 2: Verify RED**

```powershell
uv run pytest tests/unit/inspection/test_quality_checks.py::test_placeholder_token_inside_numeric_column_is_reported_verbatim -v
```

- [ ] **Step 3: Implement conservative classification helpers**

```python
PLACEHOLDER_TOKENS = {"nd", "na", "n/a", "-"}
IDENTIFIER_HEADERS = {
    "sample",
    "sample_id",
    "sample id",
    "id",
    "name",
    "sample_name",
    "sample name",
}


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

A column is numeric-looking only when:

```text
numeric_count >= 2
numeric_count / nonblank_count >= 0.60
```

Unexpected raw text all in `PLACEHOLDER_TOKENS` -> `PLACEHOLDER_TOKEN_IN_NUMERIC_COLUMN`, `WARNING`.
Other unexpected text -> `MIXED_NUMERIC_TEXT`, `WARNING`.

The issue message includes numeric and unexpected-text counts; `observed` contains distinct unexpected tokens in first-observed order, limited to 10.

- [ ] **Step 4: Add blank-value INFO reporting**

For each column with raw blanks, emit `BLANK_VALUES_PRESENT`, `INFO`, with `observed=("count:<N>",)` and the column location. Do not impute or reinterpret blanks.

- [ ] **Step 5: Implement conservative duplicate-identifier evidence**

Only columns whose normalized header is in `IDENTIFIER_HEADERS` are eligible.

For repeated nonblank values emit:

```text
code=POSSIBLE_DUPLICATE_IDENTIFIER
severity=WARNING
observed=<distinct repeated identifiers, first-observed order, max 10>
location=column:<raw header>
```

Add regression test:

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

    assert not any(
        issue.code == "POSSIBLE_DUPLICATE_IDENTIFIER"
        for issue in issues
    )
```

- [ ] **Step 6: Verify quality suite and commit**

```powershell
uv run pytest tests/unit/inspection/test_quality_checks.py -v
git add src/biostatviz/inspection/checks.py tests/unit/inspection/test_quality_checks.py
git commit -m "feat: add basic table quality checks"
```

---

### Task 6: Implement `inspect_table()` and ambiguity orchestration

**Files:**
- Create: `src/biostatviz/inspection/inspector.py`
- Modify: `src/biostatviz/inspection/__init__.py`
- Create: `tests/unit/inspection/test_inspector.py`

**Interfaces:**

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
    ...
```

There is deliberately no `safe_fixes` argument.

- [ ] **Step 1: Write clean CSV RED test**

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

- [ ] **Step 2: Verify RED**

```powershell
uv run pytest tests/unit/inspection/test_inspector.py::test_clean_csv_has_no_blocking_issues -v
```

- [ ] **Step 3: Implement common file validation**

Reuse `TableNotFoundError`, `UnsupportedTableFormatError`, and `ExcelSheetNotFoundError` from Module 01. Only `.csv` and `.xlsx` enter preview readers.

- [ ] **Step 4: Assemble CSV inspection deterministically**

Create a base option before preview:

```python
base_options = LoadingOptions(
    delimiter=delimiter or ",",
    encoding=encoding,
)
```

After preview:

- if `preview.delimiter is None` because top delimiter candidates tie, return an `InspectionReport` containing `DELIMITER_AMBIGUOUS`, `ACTION_REQUIRED`;
- candidate strings are literal delimiters in fixed candidate order;
- candidate loading options are:

```python
replace(base_options, delimiter=candidate)
```

for every tied delimiter;
- do not run header/quality checks until delimiter is resolved;
- if delimiter is resolved, set `base_options = replace(base_options, delimiter=preview.delimiter)` and run structural analysis;
- run quality analysis only when structural analysis has a single non-ambiguous `header_row`;
- issue order is format ambiguity -> structural -> quality;
- candidate loading options are deduplicated by dataclass value while preserving order.

- [ ] **Step 5: Write XLSX multiple-plausible-sheet test**

Create `Raw` and `Summary` as >=2x2 tables and `Notes` as one free-text cell. Assert:

```python
issue = next(
    issue for issue in report.issues
    if issue.code == "MULTIPLE_PLAUSIBLE_SHEETS"
)
assert issue.severity is InspectionSeverity.ACTION_REQUIRED
assert issue.candidates == ("Raw", "Summary")
assert report.inspected_sheet is None
assert [o.sheet_name for o in report.candidate_loading_options] == ["Raw", "Summary"]
```

- [ ] **Step 6: Implement XLSX sheet-selection rules**

If the caller supplies `sheet_name`:

- resolve integer index to the corresponding workbook sheet name for inspection;
- invalid string or index -> `ExcelSheetNotFoundError`;
- inspect that selected sheet;
- `base_options = LoadingOptions(sheet_name=sheet_name)` so candidate header options retain the caller's exact sheet selector;
- preserve every workbook `SheetSummary` in `report.sheets`.

If no sheet is supplied:

- one worksheet -> inspect it with `base_options=LoadingOptions(sheet_name=0)` and `inspected_sheet=<actual sheet name>`;
- multiple worksheets, exactly one plausible table -> inspect that sheet with `base_options=LoadingOptions(sheet_name=<sheet name>)`;
- >=2 plausible tables -> `MULTIPLE_PLAUSIBLE_SHEETS`, `ACTION_REQUIRED`, no sheet content inspection, one `LoadingOptions(sheet_name=name)` candidate per plausible sheet;
- zero plausible tables -> `NO_PLAUSIBLE_TABLE_SHEET`, `ACTION_REQUIRED`, candidates are all sheet names, no automatic selection.

- [ ] **Step 7: Add source-byte immutability test**

```python
before = path.read_bytes()
report = inspect_table(path)
after = path.read_bytes()
assert after == before
```

- [ ] **Step 8: Export `inspect_table` and run core tests**

```powershell
uv run pytest tests/unit/inspection/test_models.py tests/unit/inspection/test_preview_csv.py tests/unit/inspection/test_preview_xlsx.py tests/unit/inspection/test_structural_checks.py tests/unit/inspection/test_quality_checks.py tests/unit/inspection/test_inspector.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add src/biostatviz/inspection tests/unit/inspection/test_inspector.py
git commit -m "feat: add deterministic table inspection"
```

---

### Task 7: Add Agent and CLI adapters over the shared report contract

**Files:**
- Create: `src/biostatviz/inspection/agent.py`
- Create: `src/biostatviz/inspection/cli.py`
- Create: `tests/unit/inspection/test_adapters.py`

**Interfaces:**

```python
def build_agent_questions(report: InspectionReport) -> tuple[str, ...]:
    ...


def format_cli_report(report: InspectionReport) -> str:
    ...


def resolve_cli_loading_options(
    report: InspectionReport,
    *,
    input_fn=input,
) -> LoadingOptions | None:
    ...
```

- [ ] **Step 1: Write failing Agent-question test**

```python
from pathlib import Path

from biostatviz.inspection import InspectionIssue, InspectionReport, InspectionSeverity
from biostatviz.inspection.agent import build_agent_questions


def test_agent_questions_are_only_for_action_required_issues():
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

- [ ] **Step 2: Implement Agent rendering without decisions**

Mappings:

```text
MULTIPLE_PLAUSIBLE_SHEETS -> ask which worksheet
POSSIBLE_HEADER_OFFSET / HEADER_ROW_AMBIGUOUS -> ask which row is the header
DELIMITER_AMBIGUOUS -> ask which delimiter
other ACTION_REQUIRED -> <message> + candidates + explicit-choice request
```

`INFO` and `WARNING` do not become questions. The adapter does not select candidates.

- [ ] **Step 3: Write and implement CLI formatter**

Expected format:

```text
[INFO] ...
[WARNING] ...
[ACTION REQUIRED] ...
  1. candidate
  2. candidate
```

All issues are rendered in report order. Formatting must not mutate the report.

- [ ] **Step 4: Implement CLI option resolution by selecting existing report candidates**

Never construct a bare option that loses previous choices.

For exactly one supported `ACTION_REQUIRED` issue family:

1. render numbered candidates;
2. parse a 1-based integer from `input_fn`;
3. map the selected issue candidate to an existing `report.candidate_loading_options` value:
   - sheet candidate -> matching `.sheet_name`;
   - `row:N` -> matching `.header == N`;
   - delimiter candidate -> matching `.delimiter`;
4. return that existing immutable `LoadingOptions` object.

If there is no action-required issue, return `None`.
If more than one independent action-required issue family exists, raise:

```python
ValueError("Multiple independent decisions require orchestration.")
```

This intentionally supports iterative workflows: choose sheet -> rerun inspection for that sheet -> choose header if needed.

- [ ] **Step 5: Prove core non-interactivity**

Test `inspect_table()` while monkeypatching `builtins.input` to raise immediately; inspection must still succeed.

Use `ast.parse()` on these files:

```text
models.py
preview.py
checks.py
inspector.py
```

and assert no import root is any of:

```python
{"openai", "anthropic", "mcp"}
```

Do not string-search comments/docstrings.

- [ ] **Step 6: Verify adapters and commit**

```powershell
uv run pytest tests/unit/inspection/test_adapters.py -v
git add src/biostatviz/inspection/agent.py src/biostatviz/inspection/cli.py tests/unit/inspection/test_adapters.py
git commit -m "feat: add inspection interaction adapters"
```

---

### Task 8: End-to-end acceptance and documentation

**Files:**
- Create: `tests/unit/inspection/test_acceptance.py`
- Modify: `README.md`

**Interfaces:**
- Validates public `inspect_table() -> explicit LoadingOptions -> load_table()` workflow.

- [ ] **Step 1: Write leading-metadata acceptance test**

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
    option = next(
        item
        for item in report.candidate_loading_options
        if item.header == 1
    )

    loaded = load_table(path, options=option)

    assert loaded.data.columns.tolist() == ["sample", "group", "intensity"]
    assert loaded.data["intensity"].tolist() == ["101", "NA", "145"]
```

- [ ] **Step 2: Add iterative XLSX sheet-choice acceptance test**

Create a workbook with plausible `Raw` and `Summary` sheets.

First inspection must return sheet `ACTION_REQUIRED` candidates. Select the existing `LoadingOptions(sheet_name="Raw")`, then call:

```python
second_report = inspect_table(path, sheet_name=selected.sheet_name)
```

Assert `second_report.inspected_sheet == "Raw"` and no sheet ambiguity remains. Then load with:

```python
loaded = load_table(path, options=selected)
```

and assert only `Raw` values are returned.

- [ ] **Step 3: Run the complete suite**

```powershell
uv run pytest -v
```

Expected: all tests PASS with no collection errors or unexpected warnings.

- [ ] **Step 4: Run smoke gates**

```powershell
uv run python -c "from biostatviz.inspection import inspect_table; r=inspect_table('examples/data/two_group_gfp.csv'); print(r.requires_user_input)"
uv run python -c "from biostatviz.io import load_table; x=load_table('examples/data/two_group_gfp.csv'); print(x.data.shape, x.source_format)"
```

Required:

```text
False
(6, 3) csv
```

- [ ] **Step 5: Add README workflow**

Document this exact public pattern:

```python
from biostatviz.inspection import inspect_table
from biostatviz.io import load_table

report = inspect_table("experiment.csv")

if report.requires_user_input:
    for issue in report.issues:
        print(issue)
else:
    loaded = load_table("experiment.csv")
```

Also state explicitly:

- inspection reports but does not clean;
- Agent and CLI use the same `InspectionReport`;
- worksheet/header/delimiter ambiguity requires explicit user choice;
- user-authored placeholder tokens are not silently converted by default loading.

- [ ] **Step 6: Verify the 10 design acceptance criteria**

Evidence must exist for every item:

1. Clean CSV/XLSX deterministic inspection.
2. Structured issues for common imperfect table structures.
3. `INFO`, `WARNING`, `ACTION_REQUIRED` each covered by tests.
4. Structural ambiguity never silently resolved.
5. Placeholder tokens/mixed text never silently coerced by default loading.
6. Core has no interaction/LLM dependency.
7. Agent and CLI consume the same `InspectionReport` model.
8. Inspection leaves source bytes unchanged.
9. All pre-existing Module 01 tests pass.
10. No Module 02 statistical profiling behavior appears in `inspection`.

- [ ] **Step 7: Commit**

```powershell
git add README.md tests/unit/inspection/test_acceptance.py
git commit -m "test: validate table inspection workflow"
```

---

## Module 01.5 Exit Gate

Do not begin Module 02 until these commands pass on the final tree:

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

Final manual review:

- Raw preview readers use stdlib `csv`/openpyxl before pandas coercion.
- `NA`, `N/A`, `ND`, and `-` remain observable as raw tokens.
- `inspect_table()` has no `safe_fixes` argument and never writes the source.
- Multiple plausible sheets are never silently selected.
- Later or tied header candidates require explicit choice.
- Raw duplicate labels are checked before pandas can rename them.
- Mixed numeric/text issues preserve raw evidence and never coerce data.
- Duplicate-identifier warnings are restricted to conservative identifier headers.
- Header candidates preserve existing delimiter/encoding/sheet choices via `dataclasses.replace()`.
- Delimiter candidates preserve encoding and NA policy.
- Agent asks but never chooses.
- CLI selects existing `LoadingOptions`; it does not recreate partial options.
- Existing `load_table(path)` and `load_table(path, sheet_name=...)` callers continue to work.
- No statistical profiling, experiment-design inference, outlier handling, or automatic cleaning exists in Module 01.5.
