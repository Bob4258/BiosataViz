# BioStatViz Workbook Batch Inspection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the previously approved Module 01.5 inspection stack that was lost from the unpushed local workspace, then add deterministic XLSX workbook batch inspection and empty-merged-range filtering without changing scientific meaning.

**Architecture:** Keep Module 01 as the deterministic loader. Recreate `biostatviz.inspection` with raw CSV/XLSX preview, structural/quality checks, table-region discovery, merged-header detection, and Agent/CLI adapters exactly as already approved. Then add a workbook layer that calls the single-sheet inspection path explicitly for every selected worksheet, aggregates immutable per-sheet results, and renders a workbook summary. XLSX geometry is based only on real nonblank cells plus merged ranges whose anchor is nonblank.

**Tech Stack:** Python 3.11, pandas >=2.2,<3.0, openpyxl >=3.1,<4.0, pytest >=8,<9, Python stdlib `csv`, Git.

## Global Constraints

- Supported data inputs remain `.csv` and `.xlsx` only.
- `inspect_workbook()` accepts `.xlsx` only.
- Inspection never mutates source files.
- Raw token inspection happens before pandas NA/type coercion.
- No automatic cleaning, imputation, normalization, biological replicate inference, control/treatment inference, or statistical-test selection.
- Empty merged ranges are formatting residue and must not participate in geometry, regions, merged-header counts, or truncation detection.
- Workbook batch mode inspects all worksheets by default and does not stop when one sheet has `ACTION_REQUIRED`.
- Workbook order is deterministic; explicit `sheets=[...]` preserves caller order.
- Agent/CLI adapters consume shared report contracts and make no scientific decisions.
- Real uploaded research/Nature workbooks are local acceptance datasets only and must never be committed as fixtures.
- Existing Module 01 behavior remains backward-compatible.
- TDD is mandatory: RED -> GREEN -> refactor while green.

---

## Final File Structure

```text
src/biostatviz/
├── __init__.py
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
    ├── regions.py
    ├── inspector.py
    ├── workbook.py
    ├── agent.py
    └── cli.py

tests/unit/
├── io/
└── inspection/
    ├── test_models.py
    ├── test_preview_csv.py
    ├── test_preview_xlsx.py
    ├── test_structural_checks.py
    ├── test_quality_checks.py
    ├── test_regions.py
    ├── test_inspector.py
    ├── test_workbook.py
    ├── test_adapters.py
    └── test_acceptance.py
```

---

### Task 1: Restore Module 01 explicit loading options and raw-token preservation

Modify IO models/loader/exports and add loading-option tests. `LoadingOptions` is immutable with `sheet_name`, `header`, `delimiter`, `encoding`, and `keep_default_na=False`. `load_table(path, sheet_name=None, *, options=None)` remains backward-compatible and rejects conflicting sheet configuration. RED proves `NA/N/A` preservation; GREEN adds explicit delimiter/header behavior and runs the complete IO regression suite.

### Task 2: Restore Module 01.5 core contracts, raw preview, structural and quality checks

Create inspection models/errors/preview/checks and tests. Public contracts are `InspectionSeverity`, `InspectionIssue`, `SheetSummary`, `InspectionReport`. CSV preview uses stdlib `csv` and deterministic delimiter candidates. XLSX preview uses openpyxl before pandas. Structural checks cover later/tied headers, duplicate raw labels, blank rows/columns. Quality checks cover placeholder tokens, mixed numeric/text, blanks, and conservative duplicate identifiers. No coercion or cleaning.

### Task 3: Restore single-sheet table-region and merged-header inspection

Create `regions.py` and `inspector.py`, extend reports with `TableRegion` and `selected_region`, and add region/inspector tests. Region discovery keeps side-by-side tables separate, may merge vertically aligned fragments separated by one blank row, and assigns deterministic IDs. Multiple regions produce `MULTIPLE_TABLE_REGIONS`; explicit A1/region-ID selection crops inspection to the selected rectangle. Meaningful merged cells in the leading header area produce `MERGED_HEADER_DETECTED` without automatic flattening.

### Task 4: Filter empty merged ranges at the XLSX preview boundary and use meaningful geometry

Write a failing synthetic regression with real data plus distant empty merged ranges/style-only cells. Filter empty-anchor merged ranges once at preview boundary. Compute effective bounds from nonblank cells plus retained merged rectangles rather than `ws.max_row/ws.max_column`. Preserve zero, False, and formula anchors. Verify no phantom region or false `REGION_SCAN_TRUNCATED`.

### Task 5: Add immutable workbook-level report models and `inspect_workbook()`

Add `WorkbookSheetResult`, `WorkbookInspectionReport`, and `inspect_workbook(path, *, sheets=None, max_rows=50, max_columns=50)`. Default inspects all worksheets in workbook order. Explicit selectors preserve caller order. Each selected sheet is inspected through `inspect_table(..., sheet_name=<explicit name>)`, so a sheet's `ACTION_REQUIRED` never blocks later sheets. Missing/duplicate selectors fail explicitly. Derived counts and source immutability are tested.

### Task 6: Add workbook Agent/CLI summaries and sheet selection helpers

Add `build_workbook_agent_summary`, `format_workbook_summary`, and `resolve_cli_sheet_selection`. Summary includes per-sheet Regions, Merged headers, INFO, WARNING, and ACTION_REQUIRED counts. CLI accepts `all`, one 1-based index, or comma-separated indices. Adapters return existing sheet names only and never mutate or re-inspect reports.

### Task 7: End-to-end synthetic acceptance and documentation

Use anonymous synthetic workbooks covering an ordinary table, meaningful merged headers plus empty distant residue, and multiple regions. Assert default all-sheet inspection, subset ordering, per-sheet counts, nonblocking behavior, and source-byte immutability. Update README with single-table and workbook-batch workflows and no-cleaning/no-semantic-inference guarantees. Run the full suite.

### Task 8: Local real-data validation, privacy gate, and branch handoff

Real uploaded research/Nature workbooks remain local-only. Validate the private multi-region workbook and the Nature multi-sheet workbook, verify empty merged/style residue does not create phantom regions/truncation, grep repository content for real filenames/article identifiers/private labels, run fresh final tests, then sync only code, synthetic tests, README, and English specs/plans to the feature branch.

## Exit Gate

```bash
PYTHONPATH=src python -m pytest -v
PYTHONPATH=src python -c "from biostatviz.inspection import inspect_table; print(inspect_table('examples/data/two_group_gfp.csv').requires_user_input)"
PYTHONPATH=src python -c "from biostatviz.io import load_table; x=load_table('examples/data/two_group_gfp.csv'); print(x.data.shape, x.source_format)"
```

Required stable outputs:

```text
pytest: all tests PASS
example inspection requires_user_input: False
(6, 3) csv
```

Additional local-only validation confirms: private one-sheet workbook -> multiple regions and merged-header issue after explicit raw-region selection; Nature multi-sheet workbook -> all 11 sheets inspected in original order; empty merged/style residue -> no phantom regions or false scan truncation; no real data or identifying experimental content committed.
