"""
MySQL adapter for Flash.
Requires: pip install mysql-connector-python
"""

from typing import Any, Dict, List, Optional
from ..filters import filters_to_sql, build_update_sql, python_type_to_sql
from ..exceptions import ConnectionError, QueryError, TransactionError


class MySQLAdapter:
    """
    MySQL backend adapter for FlashDB.
    Uses mysql-connector-python under the hood.
    """

    def __init__(self, config: dict):
        self.config = config
        self.conn = None
        self.cursor = None
        self._in_transaction = False
        self._connect()

    def _connect(self):
        try:
            import mysql.connector
            self.conn = mysql.connector.connect(
                host=self.config.get("host", "localhost"),
                port=self.config.get("port", 3306),
                user=self.config.get("user", "root"),
                password=self.config.get("password", ""),
                database=self.config.get("database"),
                autocommit=True,
            )
            self.cursor = self.conn.cursor(dictionary=True)
        except ImportError:
            raise ConnectionError(
                "mysql-connector-python is not installed. Run: pip install mysql-connector-python"
            )
        except Exception as e:
            raise ConnectionError(f"MySQL connection failed: {e}")

    def _execute(self, sql: str, params: list = None) -> Any:
        try:
            self.cursor.execute(sql, params or [])
            return self.cursor
        except Exception as e:
            raise QueryError(f"MySQL query failed: {e}\nSQL: {sql}\nParams: {params}")

    # ── Core CRUD ──────────────────────────────────────────────────────────

    def all(self, table: str) -> List[dict]:
        self._execute(f"SELECT * FROM `{table}`")
        return self.cursor.fetchall()

    def select(self, table: str, fields: List[str] = None, filters: dict = None,
               limit: int = None, offset: int = None, order_by: str = None) -> List[dict]:
        cols = ", ".join(f"`{f}`" for f in fields) if fields else "*"
        sql = f"SELECT {cols} FROM `{table}`"
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
        return self.cursor.fetchall()

    def add(self, table: str, data: dict) -> int:
        fields = ", ".join(f"`{k}`" for k in data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        sql = f"INSERT INTO `{table}` ({fields}) VALUES ({placeholders})"
        self._execute(sql, list(data.values()))
        if not self._in_transaction:
            self.conn.commit()
        return self.cursor.lastrowid

    def bulk_insert(self, table: str, records: List[dict]) -> int:
        if not records:
            return 0
        fields = ", ".join(f"`{k}`" for k in records[0].keys())
        placeholders = ", ".join(["%s"] * len(records[0]))
        sql = f"INSERT INTO `{table}` ({fields}) VALUES ({placeholders})"
        rows = [list(r.values()) for r in records]
        try:
            self.cursor.executemany(sql, rows)
            if not self._in_transaction:
                self.conn.commit()
            return self.cursor.rowcount
        except Exception as e:
            raise QueryError(f"MySQL bulk insert failed: {e}")

    def update(self, table: str, filters: dict, data: dict) -> int:
        set_clause, set_params = build_update_sql(data)
        where_clause, where_params = filters_to_sql(filters)
        sql = f"UPDATE `{table}` SET {set_clause}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        self._execute(sql, set_params + where_params)
        if not self._in_transaction:
            self.conn.commit()
        return self.cursor.rowcount

    def delete(self, table: str, filters: dict = None) -> int:
        sql = f"DELETE FROM `{table}`"
        params = []
        if filters:
            clause, params = filters_to_sql(filters)
            sql += f" WHERE {clause}"
        self._execute(sql, params)
        if not self._in_transaction:
            self.conn.commit()
        return self.cursor.rowcount

    # ── Schema Operations ──────────────────────────────────────────────────

    def create_table(self, table: str, schema: dict, primary_key: str = "id") -> bool:
        col_defs = []
        has_pk = False
        for col, typ in schema.items():
            sql_type = python_type_to_sql(typ, "mysql")
            if col == primary_key:
                col_defs.append(f"`{col}` {sql_type} AUTO_INCREMENT PRIMARY KEY")
                has_pk = True
            else:
                col_defs.append(f"`{col}` {sql_type}")
        if not has_pk:
            col_defs.insert(0, f"`{primary_key}` INT AUTO_INCREMENT PRIMARY KEY")

        sql = f"CREATE TABLE IF NOT EXISTS `{table}` ({', '.join(col_defs)})"
        self._execute(sql)
        return True

    def drop_table(self, table: str) -> bool:
        self._execute(f"DROP TABLE IF EXISTS `{table}`")
        return True

    def truncate(self, table: str) -> bool:
        self._execute(f"TRUNCATE TABLE `{table}`")
        return True

    def show_tables(self) -> List[str]:
        self._execute("SHOW TABLES")
        rows = self.cursor.fetchall()
        return [list(r.values())[0] for r in rows]

    def describe(self, table: str) -> List[dict]:
        self._execute(f"DESCRIBE `{table}`")
        return self.cursor.fetchall()

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
            return self.cursor.fetchall()
        except Exception:
            return self.cursor.rowcount

    # ── Count ──────────────────────────────────────────────────────────────

    def count(self, table: str, filters: dict = None) -> int:
        sql = f"SELECT COUNT(*) as cnt FROM `{table}`"
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
            self.conn.ping(reconnect=True)
            return True
        except Exception:
            return False