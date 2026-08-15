"""Data contracts returned by BioStatViz IO functions."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd


@dataclass(frozen=True, slots=True)
class LoadedTable:
    """A loaded table plus immutable source metadata."""

    data: pd.DataFrame
    source_path: Path
    source_format: Literal["csv", "xlsx"]
    sheet_name: str | int | None = None
