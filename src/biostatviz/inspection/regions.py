"""Deterministic XLSX table-region discovery from raw occupied geometry."""

from __future__ import annotations

from dataclasses import dataclass

from .models import TableRegion
from .preview import TablePreview


@dataclass(frozen=True, slots=True)
class _Fragment:
    cells: frozenset[tuple[int, int]]
    @property
    def min_row(self): return min(r for r, _ in self.cells)
    @property
    def max_row(self): return max(r for r, _ in self.cells)
    @property
    def min_col(self): return min(c for _, c in self.cells)
    @property
    def max_col(self): return max(c for _, c in self.cells)
    @property
    def width(self): return self.max_col - self.min_col + 1
    @property
    def height(self): return self.max_row - self.min_row + 1


def _is_blank(value): return value is None or (isinstance(value, str) and not value.strip())


def _occupied_cells(preview: TablePreview) -> set[tuple[int, int]]:
    occupied = set()
    for ro, row in enumerate(preview.rows):
        sr = preview.origin_row + ro
        for co, value in enumerate(row):
            if not _is_blank(value): occupied.add((sr, preview.origin_col + co))
    if not preview.rows: return occupied
    min_row = preview.origin_row; max_row = preview.origin_row + len(preview.rows) - 1
    min_col = preview.origin_col; max_col = preview.origin_col + max((len(r) for r in preview.rows), default=0) - 1
    for merged in preview.merged_ranges:
        r1=max(min_row,merged.min_row); r2=min(max_row,merged.max_row); c1=max(min_col,merged.min_col); c2=min(max_col,merged.max_col)
        if r1>r2 or c1>c2: continue
        for r in range(r1,r2+1):
            for c in range(c1,c2+1): occupied.add((r,c))
    return occupied


def _components(occupied):
    remaining=set(occupied); result=[]
    while remaining:
        start=min(remaining); stack=[start]; component=set(); remaining.remove(start)
        while stack:
            cell=stack.pop(); component.add(cell); r,c=cell
            for n in ((r-1,c),(r+1,c),(r,c-1),(r,c+1)):
                if n in remaining: remaining.remove(n); stack.append(n)
        f=_Fragment(frozenset(component))
        if len(component)>=2 and f.width>=2: result.append(f)
    return sorted(result,key=lambda f:(f.min_row,f.min_col,f.max_row,f.max_col))


def _can_merge_vertical(a,b):
    if a.min_row>b.min_row: a,b=b,a
    if a.max_row>=b.min_row: return False
    gap=b.min_row-a.max_row-1
    if gap>1: return False
    overlap=max(0,min(a.max_col,b.max_col)-max(a.min_col,b.min_col)+1)
    return overlap>0 and overlap/min(a.width,b.width)>=0.75 and abs(a.min_col-b.min_col)<=1


def _merge_fragments(fragments):
    current=list(fragments); changed=True
    while changed:
        changed=False; used=[False]*len(current); out=[]
        for i,first in enumerate(current):
            if used[i]: continue
            merged=first; used[i]=True
            for j in range(i+1,len(current)):
                if not used[j] and _can_merge_vertical(merged,current[j]):
                    merged=_Fragment(merged.cells|current[j].cells); used[j]=True; changed=True
            out.append(merged)
        current=sorted(out,key=lambda f:(f.min_row,f.min_col,f.max_row,f.max_col))
    return current


def _value_at(preview,row,col):
    ro=row-preview.origin_row; co=col-preview.origin_col
    if ro<0 or ro>=len(preview.rows): return None
    source=preview.rows[ro]
    return source[co] if 0<=co<len(source) else None


def _preview_values(preview,fragment):
    values=[]; seen=set()
    for row,col in sorted(fragment.cells):
        value=_value_at(preview,row,col)
        if _is_blank(value): continue
        text=str(value).strip()
        if text and text not in seen:
            seen.add(text); values.append(text)
            if len(values)>=6: break
    return tuple(values)


def _overlaps(f,min_row,max_row,min_col,max_col):
    return not (f.max_row<min_row or f.min_row>max_row or f.max_col<min_col or f.min_col>max_col)


def discover_regions(preview: TablePreview) -> tuple[tuple[TableRegion,...], bool]:
    fragments=_merge_fragments(_components(_occupied_cells(preview)))
    finals=[f for f in fragments if f.height>=2 and f.width>=2 and len(f.cells)>=4]
    finals.sort(key=lambda f:(f.min_row,f.min_col,f.max_row,f.max_col))
    regions=[]
    for index,f in enumerate(finals,start=1):
        merged_ranges=tuple(m.a1_range for m in preview.merged_ranges if _overlaps(f,m.min_row,m.max_row,m.min_col,m.max_col))
        regions.append(TableRegion(region_id=f"region:{index}",sheet_name=preview.sheet_name or "",min_row=f.min_row,max_row=f.max_row,min_col=f.min_col,max_col=f.max_col,non_empty_cells=len(f.cells),preview_values=_preview_values(preview,f),merged_ranges=merged_ranges))
    scanned_rows=len(preview.rows); scanned_columns=max((len(r) for r in preview.rows),default=0)
    scan_last_row=preview.origin_row+scanned_rows-1 if scanned_rows else 0
    scan_last_col=preview.origin_col+scanned_columns-1 if scanned_columns else 0
    truncated=preview.apparent_rows>scan_last_row or preview.apparent_columns>scan_last_col
    return tuple(regions),truncated
