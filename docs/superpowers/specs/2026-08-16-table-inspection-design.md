# BioStatViz Module 01.5: Table Inspection Design

Date: 2026-08-16
Status: Approved design, pending implementation plan

## 1. Goal

Add a deterministic inspection layer between raw user files and `load_table()` so BioStatViz can recognize common structural problems and basic data-quality risks in imperfect scientific CSV/XLSX files without silently changing their meaning.

The same inspection core must serve both AI-agent/MCP workflows and interactive CLI workflows. Interaction belongs at the adapter layer; inspection itself remains deterministic and non-interactive.

## 2. Scope

Module 01.5 answers:

> Can BioStatViz reliably understand how this table should be read, and are there basic quality conditions the user should know about before analysis?

It includes:

- CSV/XLSX structural inspection.
- Worksheet discovery and ambiguity detection.
- Header-position plausibility checks.
- Detection of blank leading rows, blank rows, blank columns, duplicate column labels, and suspicious mixed-type columns.
- Detection of common placeholder-like tokens such as `ND`, `NA`, `N/A`, and `-` when they appear inside otherwise numeric-looking columns.
- Detection of duplicate sample-like values only when a candidate identifier column can be identified structurally; the module must report the evidence and must not infer experimental meaning.
- Risk classification into `INFO`, `WARNING`, and `ACTION_REQUIRED`.
- A structured report usable by both Agent/MCP and CLI adapters.
- Optional explicitly requested safe loading adjustments, with a default of no automatic adjustment.

It does not include:

- Choosing control/treatment groups.
- Inferring biological replicates or experimental design.
- Selecting statistical tests.
- Removing outliers.
- Imputing missing values.
- Converting biological placeholders such as `ND` to `NaN` without explicit user instruction.
- Standardization, normalization, scaling, batch correction, or transformation.
- Arbitrary Python execution.
- General Dataset Profiling; that remains Module 02.

## 3. Design Principles

### 3.1 Inspect first, decide second

Inspection must never silently resolve ambiguous scientific meaning. The core reports evidence, candidate interpretations, and risk level. A caller then decides whether to continue, ask the user, or supply explicit loading options.

### 3.2 Shared core, separate interaction adapters

The core inspection package must contain no `input()`, terminal prompts, LLM calls, MCP transport code, or UI code.

Both of these consume the same `InspectionReport`:

- Agent/MCP adapter: converts structured issues into natural-language questions and tool responses.
- CLI adapter: renders the same issues in the terminal and prompts the user when required.

### 3.3 No modification by default

Inspection never modifies the source file and never applies fixes. Detection and modification are separate concepts.

A future orchestration/adapter option may allow explicitly enabled safe loading adjustments, but any operation that can change scientific interpretation is never a safe fix.

### 3.4 Deterministic and testable

Given the same file bytes and inspection options, the core must return the same report. No LLM inference is allowed inside the inspection core.

### 3.5 Inspect raw representation before semantic coercion

Inspection must preserve enough of the raw file representation to detect tokens before pandas or another parser silently assigns meaning to them.

For example, strings such as `NA`, `N/A`, or similar tokens may be interpreted automatically as missing values by common dataframe parsers. BioStatViz must detect and report such raw tokens before they are irreversibly hidden by parser inference.

If Module 01 needs new parser options to preserve user-authored tokens, those changes must be explicit, deterministic, backward-tested, and included in the Module 01.5 implementation plan.

## 4. Proposed Architecture

```text
CSV / XLSX file
      |
      v
raw preview / workbook inspection
      |
      v
inspect_table()
      |
      +-- format / sheet discovery
      +-- structural checks
      +-- raw-token checks
      +-- basic quality checks
      +-- issue severity classification
      |
      v
InspectionReport
      |
      +----------------------+----------------------+
      |                                             |
      v                                             v
Agent / MCP adapter                          CLI adapter
structured questions                        terminal prompts
      |                                             |
      +----------------------+----------------------+
                             |
                             v
                       user decision
                             |
                             v
                       LoadingOptions
                             |
                             v
                         load_table()
                             |
                             v
                         LoadedTable
```

Module boundaries:

```text
Module 01   = deterministic table loading
Module 01.5 = structural + basic quality inspection
Module 02   = statistical dataset profiling
```

## 5. Core Public API

### 5.1 `inspect_table`

Proposed public entry point:

```python
report = inspect_table(
    path,
    sheet_name=None,
)
```

The exact final signature may be refined during the implementation plan, but the public behavior is fixed:

- It never modifies the source file.
- It never applies safe fixes or cleaning operations.
- It does not silently mutate returned user data.
- It can inspect a named Excel sheet when explicitly supplied.
- When no sheet is supplied, it reports available sheets and any ambiguity rather than guessing when several plausible data sheets exist.

### 5.2 `InspectionSeverity`

```python
INFO
WARNING
ACTION_REQUIRED
```

Semantics:

- `INFO`: useful context; does not block loading.
- `WARNING`: likely relevant to later analysis; loading may continue.
- `ACTION_REQUIRED`: interpretation is ambiguous enough that BioStatViz must not choose for the user.

### 5.3 `InspectionIssue`

Each issue should be structured rather than stored only as prose. Minimum fields:

```text
code
severity
message
location
observed
candidates
suggested_action
```

Examples of stable issue codes:

```text
MULTIPLE_PLAUSIBLE_SHEETS
POSSIBLE_HEADER_OFFSET
DUPLICATE_COLUMN_NAMES
BLANK_COLUMN
BLANK_ROW
MIXED_NUMERIC_TEXT
PLACEHOLDER_TOKEN_IN_NUMERIC_COLUMN
POSSIBLE_DUPLICATE_IDENTIFIER
PARSER_MISSING_VALUE_COERCION_RISK
```

Stable codes allow Agent, CLI, tests, and future UIs to consume the same report without parsing human-readable strings.

### 5.4 `InspectionReport`

Minimum behavior:

```text
source_path
source_format
sheets
inspected_sheet
shape_preview
issues
requires_user_input
has_warnings
```

`requires_user_input` is true when at least one `ACTION_REQUIRED` issue exists.

The report may also expose candidate loading options when the core can safely enumerate alternatives, such as candidate sheets or candidate header rows.

### 5.5 `LoadingOptions`

User decisions should become explicit configuration rather than hidden state. Examples:

```text
sheet_name="Raw"
header=3
delimiter=";"
encoding="utf-8-sig"
missing_value_policy="preserve"
```

Module 01 should only gain loading options that have explicit, deterministic semantics and are covered by tests.

`LoadingOptions` records user decisions; it does not itself imply that BioStatViz may clean data.

## 6. Detection Rules

### 6.1 Excel worksheet ambiguity

For XLSX files, inspect workbook sheet names and lightweight structural summaries.

If one sheet is clearly empty or note-like and another is tabular, the report may recommend a sheet, but recommendation alone does not authorize loading it when ambiguity remains.

If two or more sheets plausibly contain primary tables, emit `ACTION_REQUIRED` with candidate sheet names.

### 6.2 Header-position plausibility

Inspect a bounded preview of leading rows.

Signals that a later row may be the true header include:

- leading rows dominated by free text or sparsely populated cells;
- a later row with several non-empty, mostly distinct labels;
- subsequent rows having a consistent rectangular structure.

The core may report candidate header rows with evidence. It must not delete leading rows automatically.

### 6.3 Blank rows and columns

- Fully blank rows inside the apparent table: `INFO` or `WARNING` depending on frequency/location.
- Fully blank columns inside the apparent table: `WARNING` because they can indicate spreadsheet layout artifacts.
- Leading blank rows that affect header interpretation may contribute to `ACTION_REQUIRED`.

### 6.4 Duplicate column labels

Duplicate labels are `ACTION_REQUIRED` if they prevent unambiguous downstream column references.

The inspection layer must report the original duplicated labels and positions. It must not accept pandas-generated suffixes such as `.1` as if those were user-authored column names.

### 6.5 Mixed numeric/text columns

If a column is predominantly numeric but contains non-numeric text, emit `WARNING` with:

- numeric count;
- non-numeric count;
- representative unexpected tokens;
- affected column name/position.

No coercion occurs automatically.

### 6.6 Placeholder-like tokens and parser coercion risk

Tokens such as `ND`, `NA`, `N/A`, `-`, or similar values may be reported when they appear inside an otherwise numeric-looking column.

The report must describe them as observed raw tokens, not assign meaning. In particular, `ND` must not be assumed to mean missing, not detected, or zero.

If the normal dataframe loading path would automatically reinterpret an observed token as missing or another semantic value, inspection must emit a parser-coercion risk issue. The user or caller must then choose an explicit loading policy.

### 6.7 Possible duplicate identifiers

This check is conservative. It may run when a column is structurally identifier-like, for example:

- high uniqueness;
- mostly text labels;
- no continuous numeric distribution;
- column name resembles generic identifiers such as `sample`, `sample_id`, `id`, or `name`.

A duplicate result is a `WARNING`, not an automatic error, because repeated identifiers can be valid in long-format or replicate data.

The core must not infer biological-replicate meaning.

## 7. Interaction Policy

### 7.1 Agent/MCP

The Agent consumes `InspectionReport` and decides what to ask.

Example:

```text
BioStatViz detected three worksheets: Raw, Summary, and Notes.
Raw and Summary both contain plausible tables, so the primary sheet is ambiguous.
Which sheet should be loaded?
```

The Agent then converts the answer into explicit `LoadingOptions` and calls Module 01.

### 7.2 CLI

The CLI renders the same structured issues, for example:

```text
[ACTION REQUIRED] Multiple plausible worksheets detected:
1. Raw      426 x 12
2. Summary   18 x 8

Select a worksheet:
```

CLI prompting code is an adapter and must not live in the inspection core.

### 7.3 Non-interactive Python use

Python users may inspect and handle the report themselves:

```python
report = inspect_table("experiment.xlsx")
if report.requires_user_input:
    ...
```

No prompt should occur unless the user explicitly invokes an interactive CLI helper.

## 8. Safe Loading Adjustments Policy

Default orchestration behavior:

```text
auto_apply_safe_adjustments = False
```

This flag belongs outside `inspect_table()`—for example in a CLI/Agent orchestration layer—not in the inspection core.

The first implementation should keep automatic adjustments intentionally minimal. A loading decision is safe only when it has deterministic semantics and does not assign biological/statistical meaning.

Potentially allowable when explicitly enabled and either unambiguous or previously confirmed by the user:

- applying a delimiter;
- applying an encoding;
- applying a header row;
- applying a worksheet;
- applying an explicit missing-value preservation policy.

Every applied adjustment must be recorded so the final load is reproducible.

Not allowed as automatic safe adjustments:

- `ND` -> `NaN`;
- `-` -> `NaN`;
- deleting duplicate samples;
- renaming sample IDs;
- dropping rows because they look abnormal;
- changing control/treatment labels;
- imputing missing values;
- normalization or scaling;
- outlier removal;
- silently coercing mixed-type scientific measurements to numeric.

## 9. Error Handling

Inspection failures should use typed exceptions separate from detected data issues.

Examples:

- file missing: existing Module 01 missing-file error may be reused or wrapped consistently;
- unsupported format: existing unsupported-format error;
- workbook cannot be opened: read/inspection error;
- inspection succeeds but finds ambiguity: return `InspectionReport` with `ACTION_REQUIRED`, not an exception.

This distinction is important:

```text
exception = BioStatViz cannot inspect the file
issue     = BioStatViz inspected the file and found something the user should decide
```

## 10. Testing Strategy

Implementation must follow TDD.

Tests should use small synthetic fixtures that model real scientific-table problems without embedding private research data.

Required test classes:

### Structural inspection

- ordinary clean CSV returns no blocking issues;
- ordinary clean XLSX returns no blocking issues;
- multiple plausible sheets produce `ACTION_REQUIRED`;
- leading metadata rows produce a header-offset candidate;
- duplicate column names are detected from the original file structure;
- blank internal rows/columns are reported.

### Basic quality inspection

- numeric column containing `ND` produces `WARNING` and preserves the raw token in inspection evidence;
- raw `NA`/`N/A` tokens that would be swallowed by parser defaults are detected before dataframe coercion;
- mixed numeric/text values produce structured evidence;
- missing values are reported without imputation;
- repeated identifier-like values produce a conservative warning;
- repeated values in an ordinary measurement column must not be mislabeled as duplicate samples.

### Safety

- inspection never changes the source file;
- default inspection does not mutate loaded data;
- no `input()` or LLM dependency exists in the core;
- `ACTION_REQUIRED` sets `requires_user_input=True`;
- `INFO` and `WARNING` alone do not require user input;
- parser-default coercion cannot hide a raw scientific token without an inspection warning or an explicit loading policy.

### Adapter contract

- Agent/MCP and CLI adapters consume the same `InspectionReport` model;
- adapter-specific rendering does not change core severity or issue codes.

## 11. Acceptance Criteria

Module 01.5 is complete when:

1. Clean CSV/XLSX files can be inspected deterministically.
2. Common imperfect-table structures are surfaced as structured issues.
3. `INFO`, `WARNING`, and `ACTION_REQUIRED` behavior is covered by tests.
4. Ambiguous structure is never silently resolved.
5. Placeholder tokens and mixed types are never silently coerced without detection and an explicit loading policy.
6. The inspection core has no interactive or LLM dependency.
7. Agent/MCP and CLI can consume the same report model.
8. Default behavior makes no data modifications or automatic loading adjustments.
9. Existing Module 01 tests continue to pass.
10. Any required Module 01 parser-option changes are explicit and regression-tested.
11. The implementation remains clearly separated from Module 02 statistical profiling.

## 12. Deferred Work

Explicitly defer until later modules or a future extension:

- domain-specific parsers for FlowJo, GraphPad Prism, MaxQuant, ImageJ/Fiji, plate-reader exports, or instrument-specific formats;
- automatic semantic interpretation of groups, controls, replicates, doses, time points, or endpoints;
- statistical outlier detection;
- automated data cleaning recipes;
- schema templates for specific assay types;
- GUI workflows.

These can later build on the stable `InspectionReport` contract without expanding the first implementation beyond its purpose.
