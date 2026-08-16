# Region Segmentation Refinement Design

Date: 2026-08-16
Status: approved

## Goal

Refine XLSX table-region discovery so scientific worksheets are not over-merged vertically across blank rows and are not over-split horizontally by single spacer columns.

## Motivation

Real scientific source-data worksheets show two recurring layout conventions:

1. A completely blank row is commonly used to separate independent tables or figure-panel datasets.
2. A single completely blank column is commonly used as a visual spacer between groups inside one table.

The previous connected-component algorithm did the opposite in some cases: it merged vertically aligned fragments across one blank row and split one table into multiple regions whenever a single blank column disconnected cell occupancy.

## Deterministic segmentation rule

Region discovery for XLSX will use a two-stage geometric segmentation.

### Stage 1: row bands

Within the meaningful worksheet geometry, identify every row that contains at least one occupied cell. A run of consecutive nonblank rows forms a row band.

A completely blank row is a hard region boundary. No automatic region merge is allowed across a blank row.

This rule is structural only. BioStatViz does not inspect labels such as `Figure`, `Control`, condition names, or biological semantics to decide where a table starts or ends.

### Stage 2: column bands inside each row band

For each row band, identify columns containing at least one occupied cell within that row band.

- A gap of exactly 1 completely blank column is treated as an internal visual spacer and does not split the region.
- A gap of 2 or more consecutive completely blank columns splits the row band into separate horizontal region candidates.

Therefore:

```text
A:D |blank| F:G |blank| I:J
```

is one region, while:

```text
A:D |blank blank ...| K:N |blank blank ...| T:W
```

is multiple regions.

### Meaningful merged cells

Existing meaningful-geometry rules remain unchanged:

- merged ranges with a nonblank anchor participate in occupancy;
- empty merged ranges are ignored;
- style-only cells do not participate in occupied geometry.

## Table-like filtering

Each row-band/column-band rectangle becomes a candidate only if it satisfies the existing minimum table-like requirements:

- height >= 2 rows;
- width >= 2 columns;
- at least 4 occupied structural cells.

Single-row titles therefore remain outside table-region results without any text-specific rule.

## Ordering

Regions are returned deterministically in reading order:

1. top to bottom by `min_row`;
2. left to right by `min_col` within the same row band.

Region IDs remain `region:1`, `region:2`, ... in that order.

## Compatibility

No public API signature changes are required.

The behavior change is limited to `discover_regions()` and its tests. `inspect_table()` and `inspect_workbook()` continue consuming the same `TableRegion` contract.

## Synthetic regression tests

Public tests must use anonymous synthetic data only.

Required cases:

1. Two vertically aligned tables separated by one blank row remain separate.
2. One table containing one-column internal spacers remains one region.
3. Two side-by-side tables separated by two or more blank columns remain separate.
4. A row band with multiple one-column spacers remains one region.
5. Meaningful merged headers still extend region geometry.
6. Existing source immutability behavior remains unchanged.

## Local real-data acceptance

Real uploaded workbooks remain local-only and are not committed.

The current acceptance targets supplied by the user are:

- one complex worksheet expected to yield 11 independent table regions;
- one complex worksheet expected to yield 4 independent table regions;
- one complex worksheet expected to yield 3 independent table regions.

These counts are local acceptance evidence only. Figure labels, article identifiers, experimental labels, source-data filenames, and real workbook contents must not be copied into public tests or repository documentation.

The previously validated multi-region private workbook must also continue to preserve widely separated side-by-side tables as separate regions.

## Non-goals

This refinement does not attempt to infer:

- figure-panel semantics;
- biological groups or controls;
- replicate meaning;
- whether two adjacent blocks should be scientifically combined;
- arbitrary visual formatting intent beyond the deterministic blank-row/blank-column geometry above.

When the geometry remains ambiguous, BioStatViz should continue exposing multiple candidate regions rather than silently combining scientific datasets.
