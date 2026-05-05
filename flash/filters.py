"""
Query filter translation utilities.
Converts Flash's unified filter syntax to SQL WHERE clauses or MongoDB query dicts.
"""

# Mapping from Flash operators to SQL and MongoDB equivalents
OPERATOR_MAP = {
    ">": {"sql": ">", "mongo": "$gt"},
    "<": {"sql": "<", "mongo": "$lt"},
    ">=": {"sql": ">=", "mongo": "$gte"},
    "<=": {"sql": "<=", "mongo": "$lte"},
    "!=": {"sql": "!=", "mongo": "$ne"},
    "=": {"sql": "=", "mongo": "$eq"},
    "in": {"sql": "IN", "mongo": "$in"},
    "not in": {"sql": "NOT IN", "mongo": "$nin"},
    "like": {"sql": "LIKE", "mongo": "$regex"},
}


def filters_to_sql(filters: dict) -> tuple:
    """
    Convert Flash filter dict to SQL WHERE clause + params list.

    Example:
        filters = {"age": {">": 18}, "name": "John"}
        -> ("age > %s AND name = %s", [18, "John"])

    Returns:
        (clause_str, params_list)
    """
    if not filters:
        return "", []

    clauses = []
    params = []

    for field, value in filters.items():
        if isinstance(value, dict):
            for op, val in value.items():
                sql_op = OPERATOR_MAP.get(op, {}).get("sql", op)
                if op in ("in", "not in"):
                    placeholders = ", ".join(["%s"] * len(val))
                    clauses.append(f"{field} {sql_op} ({placeholders})")
                    params.extend(val)
                else:
                    clauses.append(f"{field} {sql_op} %s")
                    params.append(val)
        else:
            clauses.append(f"{field} = %s")
            params.append(value)

    return " AND ".join(clauses), params


def filters_to_mongo(filters: dict) -> dict:
    """
    Convert Flash filter dict to MongoDB query dict.

    Example:
        filters = {"age": {">": 18}, "name": "John"}
        -> {"age": {"$gt": 18}, "name": "John"}
    """
    if not filters:
        return {}

    query = {}

    for field, value in filters.items():
        if isinstance(value, dict):
            mongo_expr = {}
            for op, val in value.items():
                mongo_op = OPERATOR_MAP.get(op, {}).get("mongo")
                if mongo_op:
                    mongo_expr[mongo_op] = val
                else:
                    mongo_expr[op] = val
            query[field] = mongo_expr
        else:
            query[field] = value

    return query


def build_update_sql(data: dict) -> tuple:
    """
    Build SQL SET clause from update data dict.

    Returns:
        (set_clause_str, params_list)
    """
    if not data:
        return "", []

    clauses = [f"{field} = %s" for field in data.keys()]
    params = list(data.values())

    return ", ".join(clauses), params


def python_type_to_sql(type_str: str, db_type: str = "mysql") -> str:
    """
    Convert Flash type strings to DB-specific SQL column types.
    """
    type_map = {
        "mysql": {
            "int": "INT",
            "integer": "INT",
            "str": "VARCHAR(255)",
            "string": "VARCHAR(255)",
            "text": "TEXT",
            "float": "FLOAT",
            "double": "DOUBLE",
            "bool": "TINYINT(1)",
            "boolean": "TINYINT(1)",
            "date": "DATE",
            "datetime": "DATETIME",
            "timestamp": "TIMESTAMP",
            "json": "JSON",
            "blob": "BLOB",
        },
        "postgres": {
            "int": "INTEGER",
            "integer": "INTEGER",
            "str": "VARCHAR(255)",
            "string": "VARCHAR(255)",
            "text": "TEXT",
            "float": "REAL",
            "double": "DOUBLE PRECISION",
            "bool": "BOOLEAN",
            "boolean": "BOOLEAN",
            "date": "DATE",
            "datetime": "TIMESTAMP",
            "timestamp": "TIMESTAMP",
            "json": "JSONB",
            "blob": "BYTEA",
        },
    }

    db_types = type_map.get(db_type, type_map["mysql"])
    return db_types.get(type_str.lower(), type_str.upper())