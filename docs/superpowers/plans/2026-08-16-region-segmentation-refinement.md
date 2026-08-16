# Region Segmentation Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine XLSX region discovery so blank rows always split tables, one blank spacer column stays inside a table, and gaps of two or more blank columns split side-by-side tables.

**Architecture:** Replace connected-component plus vertical-merge behavior inside `discover_regions()` with deterministic row-band segmentation followed by column-gap segmentation. Keep the public `TableRegion` contract, meaningful merged-cell occupancy, ordering, and truncation behavior unchanged.

**Tech Stack:** Python 3.11 target, openpyxl, pytest.

## Global Constraints

- No public API signature changes.
- Completely blank row = hard region boundary.
- Exactly one blank column = internal spacer; do not split.
- Two or more consecutive blank columns = horizontal region boundary.
- Meaningful merged ranges still contribute occupied cells; empty merged ranges and style-only cells remain ignored upstream.
- Candidate region requirements remain height >= 2, width >= 2, occupied structural cells >= 4.
- No Figure/Control/biological semantic rules.
- Real uploaded workbooks remain local-only and must not enter repository tests or docs.

---

### Task 1: Lock the new segmentation semantics with failing unit tests

**Files:**
- Modify: `tests/unit/inspection/test_regions.py`
- Modify: `tests/unit/inspection/test_workbook.py`

**Interfaces:**
- Consumes: `discover_regions(preview: TablePreview) -> tuple[tuple[TableRegion, ...], bool]`
- Produces: regression expectations for blank-row boundaries and blank-column gap thresholds.

- [ ] **Step 1: Replace the old one-blank-row merge expectation** with a test asserting `A1:B2` and `A4:B5` remain separate.
- [ ] **Step 2: Replace the old one-blank-column split expectation** with a test asserting `A1:E3` remains one region.
- [ ] **Step 3: Add a two-blank-column side-by-side test** asserting `A1:B3` and `E1:F3` remain separate.
- [ ] **Step 4: Add a multiple one-column spacer test** asserting `A1:J3` remains one region for occupied blocks `A:D`, `F:G`, and `I:J`.
- [ ] **Step 5: Update workbook synthetic fixture** so its intentionally multi-region sheet uses at least two blank columns, preserving workbook-level `region_count == 2` coverage.
- [ ] **Step 6: Run the focused tests and verify RED**:

```bash
PYTHONPATH=src pytest -q tests/unit/inspection/test_regions.py tests/unit/inspection/test_workbook.py
```

Expected: failures caused by current connected-component/vertical-merge behavior.

### Task 2: Implement row-band plus column-gap segmentation

**Files:**
- Modify: `src/biostatviz/inspection/regions.py`
- Test: `tests/unit/inspection/test_regions.py`

**Interfaces:**
- Consumes: `_occupied_cells(preview)` and existing `_Fragment`/`TableRegion` helpers.
- Produces: deterministic fragments segmented by row bands and horizontal gaps.

- [ ] **Step 1: Add a helper that builds consecutive occupied row bands** from the occupied-cell set.
- [ ] **Step 2: Add a helper that finds occupied column runs inside each row band**, merging runs across exactly one blank column and splitting when the gap is >= 2.
- [ ] **Step 3: Build `_Fragment` objects from occupied cells inside each row-band/column-band rectangle.**
- [ ] **Step 4: Remove the old connected-component vertical auto-merge path from `discover_regions()`.**
- [ ] **Step 5: Preserve existing candidate filtering, merged-range reporting, preview values, deterministic ordering, and truncation calculation.**
- [ ] **Step 6: Run focused region tests and verify GREEN**:

```bash
PYTHONPATH=src pytest -q tests/unit/inspection/test_regions.py
```

Expected: all region tests pass.

### Task 3: Run full regression and local real-data acceptance

**Files:**
- No production changes unless a failing test exposes a root cause covered by the approved spec.

**Interfaces:**
- Consumes: `inspect_workbook()` and `inspect_table()` using the refined `discover_regions()`.
- Produces: verification evidence only; real workbooks are not committed.

- [ ] **Step 1: Run full repository tests**:

```bash
PYTHONPATH=src pytest -q
```

Expected: 0 failures.

- [ ] **Step 2: Run local acceptance against the uploaded complex workbook** and assert the user-supplied ground truth:

```text
complex sheet A -> 11 regions
complex sheet B -> 4 regions
complex sheet C -> 3 regions
```

- [ ] **Step 3: Re-run the previously validated widely separated side-by-side workbook** and verify its separated horizontal tables remain distinct.
- [ ] **Step 4: Verify both uploaded source workbooks are byte-identical before/after inspection.**
- [ ] **Step 5: Scan tracked source/tests/docs for real workbook names, article identifiers, Figure labels, and experiment labels; require zero private-fixture leakage.**
- [ ] **Step 6: Commit only the intended source, anonymous tests, plan/spec, and any necessary documentation changes to `feature/table-inspection`.
