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
