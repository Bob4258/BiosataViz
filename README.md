# BioStatViz

BioStatViz is an open-source toolkit for reproducible scientific statistics and visualization in AI-agent workflows.

## Development status

BioStatViz is under active development. Version 0.1 is being built and validated module by module.

## Current module

Module 01 focuses on deterministic CSV/XLSX loading with explicit validation and typed errors.

## License

MIT

## Module 01: table loading

```python
from biostatviz.io import load_table

loaded = load_table("examples/data/two_group_gfp.csv")
print(loaded.data)
```

Supported formats in v0.1 are CSV (`.csv`) and Excel (`.xlsx`). BioStatViz raises typed errors for missing files, unsupported formats, unreadable files, and missing Excel sheets instead of silently falling back to another interpretation.

## Module 01.5: table inspection

BioStatViz can inspect imperfect CSV/XLSX structure before analysis without silently cleaning or reinterpreting the source data.

```python
from biostatviz.inspection import inspect_table

report = inspect_table("experiment.xlsx", sheet_name="Data")

for issue in report.issues:
    print(issue.code, issue.severity, issue.message)
```

Inspection can report delimiter/header ambiguity, raw duplicate labels, blank structure, placeholder tokens, mixed numeric/text values, multiple XLSX table regions, and merged header cells. These findings are evidence for an explicit user decision; the inspection core does not infer controls, replicates, or biological meaning.

User-authored placeholder-like strings such as `NA`, `N/A`, `ND`, and `-` are not silently converted by default table loading.

### Workbook batch inspection

For scientific source-data workbooks where each worksheet is an independent dataset, inspect all sheets first:

```python
from biostatviz.inspection import inspect_workbook

workbook_report = inspect_workbook("source_data.xlsx")

for sheet in workbook_report.sheets:
    print(
        sheet.sheet_name,
        sheet.region_count,
        sheet.merged_header_count,
        sheet.action_required_count,
    )
```

`inspect_workbook()` checks every worksheet in workbook order by default. A warning or required decision in one sheet does not stop inspection of later sheets. Callers may also restrict the batch explicitly, for example `sheets=["Data A", "Data C"]`.

Empty merged ranges and style-only spreadsheet residue are ignored as structural geometry. Only real nonblank cell values and merged ranges with a nonblank anchor participate in table-region and merged-header detection.
