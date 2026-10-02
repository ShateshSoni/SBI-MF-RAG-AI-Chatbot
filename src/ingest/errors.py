"""Ingestion errors that must stop a document rather than skip it silently."""


class FetchError(Exception):
    """Raised when a document cannot be downloaded under the allowlist rules."""


class ParseError(Exception):
    """Raised when a document yields no usable blocks."""
