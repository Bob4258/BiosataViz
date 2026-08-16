"""Typed failures that prevent deterministic table inspection."""

from biostatviz.io import BioStatVizIOError


class InspectionError(BioStatVizIOError):
    """Base class for failures that prevent inspection."""


class InspectionReadError(InspectionError):
    """Raised when a supported file cannot be previewed for inspection."""


class RegionSelectionError(InspectionError):
    """Raised when an XLSX table-region selector is invalid."""
