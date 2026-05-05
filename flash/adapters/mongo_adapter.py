"""
MongoDB adapter for Flash.
Requires: pip install pymongo
"""

from typing import Any, Dict, List, Optional
from ..filters import filters_to_mongo
from ..exceptions import ConnectionError, QueryError


class MongoAdapter:
    """
    MongoDB backend adapter for FlashDB.
    Uses pymongo under the hood.
    """

    def __init__(self, config: dict):
        self.config = config
        self.client = None
        self.db = None
        self._connect()

    def _connect(self):
        try:
            from pymongo import MongoClient
            from pymongo.errors import ConnectionFailure

            uri = self.config.get("uri")
            if uri:
                self.client = MongoClient(uri)
            else:
                host = self.config.get("host", "localhost")
                port = self.config.get("port", 27017)
                user = self.config.get("user")
                password = self.config.get("password")

                if user and password:
                    self.client = MongoClient(
                        host=host, port=port, username=user, password=password
                    )
                else:
                    self.client = MongoClient(host=host, port=port)

            db_name = self.config.get("database", "flash_db")
            self.db = self.client[db_name]

            # Test connection
            self.client.admin.command("ping")

        except ImportError:
            raise ConnectionError(
                "pymongo is not installed. Run: pip install pymongo"
            )
        except Exception as e:
            raise ConnectionError(f"MongoDB connection failed: {e}")

    def _col(self, table: str):
        """Return the pymongo Collection for the given table/collection name."""
        return self.db[table]

    def _clean(self, doc) -> dict:
        """Convert ObjectId to string for clean output."""
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc

    # ── Core CRUD ──────────────────────────────────────────────────────────

    def all(self, table: str) -> List[dict]:
        return [self._clean(d) for d in self._col(table).find()]

    def select(self, table: str, fields: List[str] = None, filters: dict = None,
               limit: int = None, offset: int = None, order_by: str = None) -> List[dict]:
        query = filters_to_mongo(filters) if filters else {}
        projection = {f: 1 for f in fields} if fields else None

        cursor = self._col(table).find(query, projection)

        if order_by:
            # Support "field" (asc) or "-field" (desc)
            if order_by.startswith("-"):
                cursor = cursor.sort(order_by[1:], -1)
            else:
                cursor = cursor.sort(order_by, 1)

        if offset:
            cursor = cursor.skip(int(offset))
        if limit:
            cursor = cursor.limit(int(limit))

        return [self._clean(d) for d in cursor]

    def add(self, table: str, data: dict) -> str:
        try:
            result = self._col(table).insert_one(data.copy())
            return str(result.inserted_id)
        except Exception as e:
            raise QueryError(f"MongoDB insert failed: {e}")

    def bulk_insert(self, table: str, records: List[dict]) -> int:
        if not records:
            return 0
        try:
            result = self._col(table).insert_many([r.copy() for r in records])
            return len(result.inserted_ids)
        except Exception as e:
            raise QueryError(f"MongoDB bulk insert failed: {e}")

    def update(self, table: str, filters: dict, data: dict) -> int:
        query = filters_to_mongo(filters)
        try:
            result = self._col(table).update_many(query, {"$set": data})
            return result.modified_count
        except Exception as e:
            raise QueryError(f"MongoDB update failed: {e}")

    def delete(self, table: str, filters: dict = None) -> int:
        query = filters_to_mongo(filters) if filters else {}
        try:
            result = self._col(table).delete_many(query)
            return result.deleted_count
        except Exception as e:
            raise QueryError(f"MongoDB delete failed: {e}")

    # ── Schema / Collection Operations ─────────────────────────────────────

    def create_table(self, table: str, schema: dict = None, primary_key: str = "id") -> bool:
        """
        In MongoDB, collections are created implicitly.
        This optionally applies a JSON Schema validator.
        """
        if schema:
            props = {}
            for field, typ in schema.items():
                bson_type = self._py_to_bson(typ)
                props[field] = {"bsonType": bson_type}

            validator = {
                "$jsonSchema": {
                    "bsonType": "object",
                    "properties": props,
                }
            }
            try:
                self.db.create_collection(table, validator=validator)
            except Exception:
                # Collection may already exist; apply collMod instead
                self.db.command("collMod", table, validator=validator)
        else:
            if table not in self.db.list_collection_names():
                self.db.create_collection(table)
        return True

    def drop_table(self, table: str) -> bool:
        self._col(table).drop()
        return True

    def truncate(self, table: str) -> bool:
        self._col(table).delete_many({})
        return True

    def show_tables(self) -> List[str]:
        return self.db.list_collection_names()

    def describe(self, table: str) -> dict:
        """Return collection stats as schema info."""
        return self.db.command("collStats", table)

    def create_index(self, table: str, field: str, unique: bool = False) -> str:
        from pymongo import ASCENDING
        result = self._col(table).create_index([(field, ASCENDING)], unique=unique)
        return result

    # ── Transactions (MongoDB 4.0+ with replica set) ───────────────────────

    def begin(self):
        self._session = self.client.start_session()
        self._session.start_transaction()

    def commit(self):
        if hasattr(self, "_session"):
            self._session.commit_transaction()
            self._session.end_session()

    def rollback(self):
        if hasattr(self, "_session"):
            self._session.abort_transaction()
            self._session.end_session()

    # ── Raw Query ──────────────────────────────────────────────────────────

    def raw(self, command: dict, table: str = None) -> Any:
        """
        Execute a raw MongoDB command.
        For collection-level ops pass table; otherwise it runs on the DB.
        """
        try:
            if table:
                return list(self._col(table).find(command))
            return self.db.command(command)
        except Exception as e:
            raise QueryError(f"MongoDB raw command failed: {e}")

    # ── Count ──────────────────────────────────────────────────────────────

    def count(self, table: str, filters: dict = None) -> int:
        query = filters_to_mongo(filters) if filters else {}
        return self._col(table).count_documents(query)

    # ── Aggregation ────────────────────────────────────────────────────────

    def aggregate(self, table: str, pipeline: list) -> List[dict]:
        return [self._clean(d) for d in self._col(table).aggregate(pipeline)]

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def close(self):
        if self.client:
            self.client.close()

    def ping(self) -> bool:
        try:
            self.client.admin.command("ping")
            return True
        except Exception:
            return False

    # ── Helpers ────────────────────────────────────────────────────────────

    def _py_to_bson(self, type_str: str) -> str:
        mapping = {
            "int": "int",
            "integer": "int",
            "str": "string",
            "string": "string",
            "text": "string",
            "float": "double",
            "double": "double",
            "bool": "bool",
            "boolean": "bool",
            "date": "date",
            "datetime": "date",
            "list": "array",
            "dict": "object",
            "json": "object",
        }
        return mapping.get(type_str.lower(), "string")