"""
Flash - A unified database interface for MySQL, PostgreSQL, and MongoDB.
"""

from .core import FlashDB
from .exceptions import FlashError, ConnectionError, QueryError

__version__ = "1.0.0"
__author__ = "Flash Team"
__all__ = ["FlashDB", "FlashError", "ConnectionError", "QueryError"]