"""Framework-independent errors raised by use cases.

The HTTP layer maps them to status codes (app/interfaces/http/errors.py), so use
cases never need to know about HTTP.
"""


class ApplicationError(Exception):
    """Base class for expected, user-facing failures."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(ApplicationError):
    """The requested resource does not exist."""


class InvalidInputError(ApplicationError):
    """The request is well-formed but violates a business rule."""
