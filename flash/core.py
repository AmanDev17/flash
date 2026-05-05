"""
Flash Core — FlashDB unified database interface.

Usage:
    from flash import FlashDB

    flash = FlashDB("mysql", config)
    flash.add("users", {"name": "John", "age": 25})
    flash.all("users")
"""

from typing import Any, Dict, List, Optional, Callable
from .exceptions import UnsupportedDatabaseError, FlashError
from .triggers import make_trigger_mixin


class FlashDB(make_trigger_mixin()):
    """
    FlashDB — a unified, trigger-aware database interface.
    Supports MySQL, PostgreSQL, and MongoDB with a single API.

    Args:
        db_type (str): One of 'mysql', 'postgres', 'mongodb'
        config (dict): Connection configuration dict.

    Example:
        flash = FlashDB("mysql", {
            "host": "localhost",
            "user": "root",
            "password": "1234",
            "database": "mydb"
        })
    """

    SUPPORTED = ("mysql", "postgres", "postgresql", "mongodb", "mongo")

    def __init__(self, db_type: str, config: dict):
        self.db_type = db_type.lower().strip()
        self.config = config
        self._init_triggers()
        self._adapter = self._load_adapter()

    def _load_adapter(self):
        if self.db_type == "mysql":
            from .adapters.mysql_adapter import MySQLAdapter
            return MySQLAdapter(self.config)

        elif self.db_type in ("postgres", "postgresql"):
            from .adapters.postgres_adapter import PostgreSQLAdapter
            return PostgreSQLAdapter(self.config)

        elif self.db_type in ("mongodb", "mongo"):
            from .adapters.mongo_adapter import MongoAdapter
            return MongoAdapter(self.config)

        else:
            raise UnsupportedDatabaseError(
                f"'{self.db_type}' is not supported. Choose from: mysql, postgres, mongodb"
            )

    # ── Read Operations ────────────────────────────────────────────────────

    def all(self, table: str) -> List[dict]:
        """Fetch all records from a table/collection."""
        self._triggers.fire("before", "select", table, {})
        result = self._adapter.all(table)
        self._triggers.fire("after", "select", table, {}, result)
        return result

    def select(
        self,
        table: str,
        fields: List[str] = None,
        filters: dict = None,
        limit: int = None,
        offset: int = None,
        order_by: str = None,
    ) -> List[dict]:
        """
        Select records with optional field projection, filters, sorting, and pagination.

        Args:
            table: Table/collection name.
            fields: List of field names to return.
            filters: Flash filter dict (e.g. {"age": {">": 18}}).
            limit: Maximum number of records.
            offset: Number of records to skip.
            order_by: Field name to sort by (prefix '-' for descending in MongoDB).

        Example:
            flash.select("users", fields=["name", "age"], filters={"age": {">": 18}}, limit=10)
        """
        payload = {"fields": fields, "filters": filters}
        self._triggers.fire("before", "select", table, payload)
        result = self._adapter.select(
            table, fields=fields, filters=filters,
            limit=limit, offset=offset, order_by=order_by
        )
        self._triggers.fire("after", "select", table, payload, result)
        return result

    def where(self, table: str, filters: dict, fields: List[str] = None) -> List[dict]:
        """
        Shorthand for filtered select.

        Example:
            flash.where("users", {"age": {">": 18}})
            flash.where("users", {"name": "John"})
        """
        return self.select(table, fields=fields, filters=filters)

    def find_one(self, table: str, filters: dict) -> Optional[dict]:
        """Return the first matching record, or None."""
        results = self.select(table, filters=filters, limit=1)
        return results[0] if results else None

    def count(self, table: str, filters: dict = None) -> int:
        """Count records in a table/collection, optionally filtered."""
        return self._adapter.count(table, filters)

    def limit(self, table: str, n: int) -> List[dict]:
        """Fetch the first N records."""
        return self.select(table, limit=n)

    def paginate(self, table: str, page: int = 1, size: int = 10) -> dict:
        """
        Paginate records.

        Returns:
            {
                "data": [...],
                "page": 1,
                "size": 10,
                "total": 42
            }
        """
        offset = (page - 1) * size
        data = self.select(table, limit=size, offset=offset)
        total = self.count(table)
        return {"data": data, "page": page, "size": size, "total": total}

    # ── Write Operations ───────────────────────────────────────────────────

    def add(self, table: str, data: dict) -> Any:
        """
        Insert a single record.

        Returns:
            Inserted ID (int for SQL, str for MongoDB).

        Example:
            flash.add("users", {"name": "John", "age": 25})
        """
        self._triggers.fire("before", "insert", table, data)
        result = self._adapter.add(table, data)
        self._triggers.fire("after", "insert", table, data, result)
        return result

    def bulk_insert(self, table: str, records: List[dict]) -> int:
        """
        Insert multiple records at once.

        Returns:
            Number of inserted records.

        Example:
            flash.bulk_insert("users", [{"name": "A"}, {"name": "B"}])
        """
        self._triggers.fire("before", "insert", table, records)
        result = self._adapter.bulk_insert(table, records)
        self._triggers.fire("after", "insert", table, records, result)
        return result

    def update(self, table: str, filters: dict, data: dict) -> int:
        """
        Update records matching filters with new data.

        Returns:
            Number of updated records.

        Example:
            flash.update("users", {"name": "John"}, {"age": 26})
        """
        payload = {"filters": filters, "data": data}
        self._triggers.fire("before", "update", table, payload)
        result = self._adapter.update(table, filters, data)
        self._triggers.fire("after", "update", table, payload, result)
        return result

    def delete(self, table: str, filters: dict = None) -> int:
        """
        Delete records matching filters. If no filters given, deletes ALL records.

        Returns:
            Number of deleted records.

        Example:
            flash.delete("users", {"name": "John"})
        """
        self._triggers.fire("before", "delete", table, filters or {})
        result = self._adapter.delete(table, filters)
        self._triggers.fire("after", "delete", table, filters or {}, result)
        return result

    # ── Schema Operations ──────────────────────────────────────────────────

    def create_table(self, table: str, schema: dict, primary_key: str = "id") -> bool:
        """
        Create a table/collection with the given schema.

        Args:
            table: Table name.
            schema: Dict of {column_name: type_string}.
            primary_key: Name of the primary key column (SQL only).

        Example:
            flash.create_table("users", {
                "id": "int",
                "name": "str",
                "email": "str",
                "age": "int"
            })
        """
        return self._adapter.create_table(table, schema, primary_key)

    def drop_table(self, table: str) -> bool:
        """Drop a table/collection entirely."""
        return self._adapter.drop_table(table)

    def truncate(self, table: str) -> bool:
        """Remove all records from a table/collection without dropping it."""
        return self._adapter.truncate(table)

    def show_tables(self) -> List[str]:
        """List all tables/collections in the database."""
        return self._adapter.show_tables()

    def describe(self, table: str):
        """Return schema/column information for a table/collection."""
        return self._adapter.describe(table)

    # ── Transactions ───────────────────────────────────────────────────────

    def begin(self):
        """Begin a transaction (SQL) or session (MongoDB 4+ replica set)."""
        self._adapter.begin()

    def commit(self):
        """Commit the current transaction."""
        self._adapter.commit()

    def rollback(self):
        """Roll back the current transaction."""
        self._adapter.rollback()

    # ── Raw Query Escape Hatch ─────────────────────────────────────────────

    def raw(self, query, params: list = None, table: str = None) -> Any:
        """
        Execute a raw query/command.

        SQL:   flash.raw("SELECT * FROM users WHERE age > %s", [18])
        Mongo: flash.raw({"name": "John"}, table="users")
        """
        return self._adapter.raw(query, params) if params is not None else self._adapter.raw(query)

    # ── MongoDB-Specific ───────────────────────────────────────────────────

    def aggregate(self, table: str, pipeline: list) -> List[dict]:
        """
        Run a MongoDB aggregation pipeline (MongoDB only).

        Example:
            flash.aggregate("orders", [
                {"$group": {"_id": "$user_id", "total": {"$sum": "$amount"}}}
            ])
        """
        if not hasattr(self._adapter, "aggregate"):
            raise FlashError("aggregate() is only available for MongoDB.")
        return self._adapter.aggregate(table, pipeline)

    def create_index(self, table: str, field: str, unique: bool = False) -> str:
        """Create an index on a MongoDB collection field."""
        if not hasattr(self._adapter, "create_index"):
            raise FlashError("create_index() is only available for MongoDB.")
        return self._adapter.create_index(table, field, unique)

    # ── Utility ────────────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Test if the database connection is alive."""
        return self._adapter.ping()

    def close(self):
        """Close the database connection."""
        self._adapter.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __repr__(self):
        return f"<FlashDB type={self.db_type} db={self.config.get('database', '?')}>"