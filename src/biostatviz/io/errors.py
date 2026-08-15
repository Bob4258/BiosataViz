"""Typed exceptions raised by the BioStatViz IO layer."""


class BioStatVizIOError(Exception):
    """Base class for BioStatViz table-loading failures."""


class TableNotFoundError(BioStatVizIOError):
    """Raised when a requested table path does not exist."""


class UnsupportedTableFormatError(BioStatVizIOError):
    """Raised when a table extension is not supported."""


class TableReadError(BioStatVizIOError):
    """Raised when a supported file cannot be parsed."""


class ExcelSheetNotFoundError(TableReadError):
    """Raised when a requested Excel sheet is unavailable."""
