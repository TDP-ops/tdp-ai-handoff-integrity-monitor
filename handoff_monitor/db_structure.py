"""Read-only bounded SQLite schema observations for db_schema typed checks.

Supports actual SQLite database files only. Does not query table rows or
execute user SQL from a manifest. Non-SQLite files/dialects abstain.
"""
import sqlite3
from pathlib import Path

MAX_DB_BYTES = 8 * 1024 * 1024
SQLITE_HEADER = b"SQLite format 3\x00"


def _identifier(name):
    # Quoted SQLite identifier: never interpolate an unquoted contract value.
    return '"' + name.replace('"', '""') + '"'


def sqlite_schema(path):
    file_path = Path(path).resolve(strict=True)
    if file_path.stat().st_size > MAX_DB_BYTES:
        raise ValueError("SQLite file exceeds limit")
    with file_path.open("rb") as stream:
        if stream.read(16) != SQLITE_HEADER:
            raise ValueError("Unsupported database format")

    # URI mode=ro prevents writes; immutable ignores journal sidecars. The
    # evaluation is a local point-in-time inspection, not a proven snapshot.
    uri = file_path.as_uri() + "?mode=ro&immutable=1"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=1)
    except sqlite3.DatabaseError as error:
        raise ValueError("Cannot open SQLite database in read-only mode") from error
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA trusted_schema=OFF")
        result = connection.execute("PRAGMA quick_check").fetchone()
        if result != ("ok",):
            raise ValueError("SQLite integrity verification failed")

        tables = {}
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        if len(rows) > 256:
            raise ValueError("Excessive SQLite tables")
        for (name,) in rows:
            columns = {}
            for column in connection.execute(
                    "PRAGMA table_info(" + _identifier(name) + ")"):
                # cid, name, type, notnull, default, pk
                if column[1] in columns:
                    raise ValueError("Duplicate SQLite column")
                columns[column[1]] = column[2].strip().upper()
            foreign_keys = set()
            for key in connection.execute(
                    "PRAGMA foreign_key_list(" + _identifier(name) + ")"):
                # id, seq, reference_table, from_column, to_column, ...
                foreign_keys.add((key[3], key[2], key[4]))
            tables[name] = (columns, foreign_keys)
        return tables
    except sqlite3.DatabaseError as error:
        raise ValueError("Unreadable SQLite schema") from error
    finally:
        connection.close()


def sqlite_schema_check(tables, check):
    """Return True/False for one precisely declared SQLite structure rule."""
    table = tables.get(check["table_name"])
    if check["check_type"] == "db_required_table":
        return table is not None
    if table is None:
        return False
    columns, foreign_keys = table
    if check["check_type"] == "db_required_column":
        expected_type = " ".join(check["data_type"].upper().split())
        observed_type = " ".join(
            columns.get(check["column_name"], "").upper().split())
        return bool(observed_type) and observed_type == expected_type
    if check["check_type"] == "db_required_foreign_key":
        return (check["column_name"], check["references_table"],
                check["references_column"]) in foreign_keys
    raise ValueError("Unsupported SQLite structure assertion")
