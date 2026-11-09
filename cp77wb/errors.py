class Cp77wbError(Exception):
    """Base exception for cp77wb."""


class ProjectFormatError(Cp77wbError):
    """Raised when a file is not a supported World Builder project."""


class PathNotFoundError(Cp77wbError):
    """Raised when a World Builder hierarchy path cannot be resolved."""
