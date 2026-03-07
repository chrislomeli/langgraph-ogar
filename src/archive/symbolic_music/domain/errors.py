"""
Domain-level errors and exceptions.
"""


class DomainError(ValueError):
    """Base class for domain-level invariant violations."""


class TimeBoundsError(DomainError):
    """Raised when event offsets/durations violate container boundaries."""


class InvalidPitchError(DomainError):
    """Raised when pitch data is invalid."""


class InvalidTimeSignatureError(DomainError):
    """Raised when time signature is invalid."""
