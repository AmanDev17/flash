"""
Custom exceptions for the Flash library.
"""


class FlashError(Exception):
    """Base exception for all Flash errors."""
    pass


class ConnectionError(FlashError):
    """Raised when a database connection fails."""
    pass


class QueryError(FlashError):
    """Raised when a query fails to execute."""
    pass


class UnsupportedDatabaseError(FlashError):
    """Raised when an unsupported database type is used."""
    pass


class TransactionError(FlashError):
    """Raised when a transaction operation fails."""
    pass


class SchemaError(FlashError):
    """Raised when a schema operation fails."""
    pass