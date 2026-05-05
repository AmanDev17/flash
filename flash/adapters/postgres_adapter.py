"""
PostgreSQL adapter for Flash.
Requires: pip install psycopg2-binary
"""

from typing import Any, Dict, List, Optional
from ..filters import filters_to_sql, build_update_sql, python_type_to_sql
from ..exceptions import ConnectionError, QueryError, TransactionError


class PostgreSQLAdapter:
    """
    PostgreSQL backend adapter for FlashDB.
    Uses psycopg2 under the hood.
    """

    def __init__(self, config: dict):
        self.config = config
        self.conn = None
        self.cursor = None
        self._in_transaction = False
        self._connect()

    def _connect(self):
        try:
            import psycopg2
            import psycopg2.extras
            self.conn = psycopg2.connect(
                host=self.config.get("host", "localhost"),
                port=self.config.get("port", 5432),
                user=self.config.get("user", "postgres"),
                password=self.config.get("password", ""),
                dbname=self.config.get("database"),
            )
            self.conn.autocommit = True
            self.cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        except ImportError:
            raise ConnectionError(
                "psycopg2 is not installed. Run: pip install psycopg2-binary"
            )
        except Exception as e:
            raise ConnectionError(f"PostgreSQL connection failed: {e}")

    def _execute(self, sql: str, params: list = None) -> Any:
        # psycopg2 uses %s but doesn't need None as []
        try:
            self.cursor.execute(sql, params if params else None)
            return self.cursor
        except Exception as e:
            if not self._in_transaction:
                self.conn.rollback()
            raise QueryError(f"PostgreSQL query failed: {e}\nSQL: {sql}\nParams: {params}")

    def _quote(self, name: str) -> str:
        return f'"{name}"'

    # ── Core CRUD ──────────────────────────────────────────────────────────

    def all(self, table: str) -> List[dict]:
        self._execute(f"SELECT * FROM {self._quote(table)}")
        return [dict(row) for row in self.cursor.fetchall()]

    def select(self, table: str, fields: List[str] = None, filters: dict = None,
               limit: int = None, offset: int = None, order_by: str = None) -> List[dict]:
        cols = ", ".join(self._quote(f) for f in fields) if fields else "*"
        sql = f"SELECT {cols} FROM {self._quote(table)}"
        params = []

        if filters:
            clause, params = filters_to_sql(filters)
            sql += f" WHERE {clause}"

        if order_by:
            sql += f" ORDER BY {order_by}"

        if limit is not None:
            sql += f" LIMIT {int(limit)}"
            if offset is not None:
                sql += f" OFFSET {int(offset)}"

        self._execute(sql, params)
        return [dict(row) for row in self.cursor.fetchall()]

    def add(self, table: str, data: dict) -> Any:
        fields = ", ".join(self._quote(k) for k in data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        sql = f"INSERT INTO {self._quote(table)} ({fields}) VALUES ({placeholders}) RETURNING *"
        self._execute(sql, list(data.values()))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def bulk_insert(self, table: str, records: List[dict]) -> int:
        if not records:
            return 0
        fields = ", ".join(self._quote(k) for k in records[0].keys())
        placeholders = ", ".join(["%s"] * len(records[0]))
        sql = f"INSERT INTO {self._quote(table)} ({fields}) VALUES ({placeholders})"
        rows = [list(r.values()) for r in records]
        try:
            self.cursor.executemany(sql, rows)
            return self.cursor.rowcount
        except Exception as e:
            raise QueryError(f"PostgreSQL bulk insert failed: {e}")

    def update(self, table: str, filters: dict, data: dict) -> int:
        set_clause, set_params = build_update_sql(data)
        where_clause, where_params = filters_to_sql(filters)
        sql = f"UPDATE {self._quote(table)} SET {set_clause}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        self._execute(sql, set_params + where_params)
        return self.cursor.rowcount

    def delete(self, table: str, filters: dict = None) -> int:
        sql = f"DELETE FROM {self._quote(table)}"
        params = []
        if filters:
            clause, params = filters_to_sql(filters)
            sql += f" WHERE {clause}"
        self._execute(sql, params)
        return self.cursor.rowcount

    # ── Schema Operations ──────────────────────────────────────────────────

    def create_table(self, table: str, schema: dict, primary_key: str = "id") -> bool:
        col_defs = []
        has_pk = False
        for col, typ in schema.items():
            sql_type = python_type_to_sql(typ, "postgres")
            if col == primary_key:
                col_defs.append(f"{self._quote(col)} SERIAL PRIMARY KEY")
                has_pk = True
            else:
                col_defs.append(f"{self._quote(col)} {sql_type}")
        if not has_pk:
            col_defs.insert(0, f"{self._quote(primary_key)} SERIAL PRIMARY KEY")

        sql = f"CREATE TABLE IF NOT EXISTS {self._quote(table)} ({', '.join(col_defs)})"
        self._execute(sql)
        return True

    def drop_table(self, table: str) -> bool:
        self._execute(f"DROP TABLE IF EXISTS {self._quote(table)}")
        return True

    def truncate(self, table: str) -> bool:
        self._execute(f"TRUNCATE TABLE {self._quote(table)} RESTART IDENTITY CASCADE")
        return True

    def show_tables(self) -> List[str]:
        sql = """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """
        self._execute(sql)
        return [row["table_name"] for row in self.cursor.fetchall()]

    def describe(self, table: str) -> List[dict]:
        sql = """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """
        self._execute(sql, [table])
        return [dict(row) for row in self.cursor.fetchall()]

    # ── Transactions ───────────────────────────────────────────────────────

    def begin(self):
        self.conn.autocommit = False
        self._in_transaction = True

    def commit(self):
        try:
            self.conn.commit()
        except Exception as e:
            raise TransactionError(f"Commit failed: {e}")
        finally:
            self.conn.autocommit = True
            self._in_transaction = False

    def rollback(self):
        try:
            self.conn.rollback()
        except Exception as e:
            raise TransactionError(f"Rollback failed: {e}")
        finally:
            self.conn.autocommit = True
            self._in_transaction = False

    # ── Raw Query ──────────────────────────────────────────────────────────

    def raw(self, sql: str, params: list = None) -> Any:
        self._execute(sql, params)
        try:
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception:
            return self.cursor.rowcount

    # ── Count ──────────────────────────────────────────────────────────────

    def count(self, table: str, filters: dict = None) -> int:
        sql = f"SELECT COUNT(*) as cnt FROM {self._quote(table)}"
        params = []
        if filters:
            clause, params = filters_to_sql(filters)
            sql += f" WHERE {clause}"
        self._execute(sql, params)
        row = self.cursor.fetchone()
        return row["cnt"] if row else 0

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def ping(self) -> bool:
        try:
            self._execute("SELECT 1")
            return True
        except Exception:
            return False