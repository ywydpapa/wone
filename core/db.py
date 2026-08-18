import os
import sqlite3

# main.py already calls dotenv.load_dotenv() before importing this module.
# Call it here too so that init_db.py (run standalone) also picks up .env.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# DATABASE_URL parsing
# ---------------------------------------------------------------------------
_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///test.db")


def _parse_db_url(url: str):
    """Return ('sqlite', path) or ('mysql', dict_of_mysql_kwargs)."""
    if url.startswith("sqlite:///"):
        # sqlite:///path  -> relative to project root (cwd) if not absolute
        path = url[len("sqlite:///"):]
        if not os.path.isabs(path):
            path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), path)
        return ("sqlite", path)
    if url.startswith("mysql://"):
        # mysql://user:pass@host:port/dbname
        rest = url[len("mysql://"):]
        user_pass, rest = rest.split("@", 1)
        if ":" in user_pass:
            user, password = user_pass.split(":", 1)
        else:
            user, password = user_pass, ""
        host_port, dbname = rest.split("/", 1)
        if ":" in host_port:
            host, port_str = host_port.split(":", 1)
            port = int(port_str)
        else:
            host, port = host_port, 3306
        return ("mysql", {"host": host, "port": port, "user": user,
                          "password": password, "database": dbname,
                          "charset": "utf8mb4"})
    raise ValueError(f"Unsupported DATABASE_URL scheme: {url!r}")


_DB_SCHEME, _DB_CONFIG = _parse_db_url(_DATABASE_URL)

# Legacy alias used by init_db.py (sqlite mode only)
DB_PATH = _DB_CONFIG if _DB_SCHEME == "sqlite" else None


# ---------------------------------------------------------------------------
# STATUS_META (unchanged)
# ---------------------------------------------------------------------------
STATUS_META = {
    "urgent":      ("긴급",  "status-urgent",   ""),
    "progress":    ("진행중", "status-progress", ""),
    "in_progress": ("진행중", "status-progress", ""),
    "wait":        ("대기",  "status-progress", "background-color:#e2e3e5; color:#383d41;"),
    "pending":     ("대기",  "status-progress", "background-color:#e2e3e5; color:#383d41;"),
    "draft":       ("임시저장", "status-progress", "background-color:#e2e3e5; color:#383d41;"),
    "withdrawn":   ("철회",    "status-progress", "background-color:#fff3cd; color:#856404;"),
    "done":        ("완료",  "status-done",     ""),
    "approved":    ("완료",  "status-done",     ""),
    "resolved":    ("완료",  "status-done",     ""),
    "rejected":    ("반려",  "status-urgent",   ""),
}


# ---------------------------------------------------------------------------
# MySQL adapter classes
# ---------------------------------------------------------------------------

class RowAdapter:
    """Wraps a single PyMySQL tuple row to behave like sqlite3.Row.

    Supports:
      row["col"]   -- key access
      row[0]       -- integer index
      dict(row)    -- conversion to plain dict
      for v in row -- iteration over values
    """

    __slots__ = ("_data", "_keys")

    def __init__(self, data: tuple, keys: tuple):
        self._data = data
        self._keys = keys  # lowercase column names

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._data[key]
        try:
            return self._data[self._keys.index(key)]
        except ValueError:
            raise KeyError(key)

    def __iter__(self):
        return iter(self._data)

    def keys(self):
        return list(self._keys)

    def __repr__(self):
        return f"<RowAdapter {dict(zip(self._keys, self._data))}>"


def _rows_to_adapters(cursor, rows):
    """Convert a list of PyMySQL tuples to RowAdapter list."""
    if cursor.description is None:
        return []
    keys = tuple(d[0] for d in cursor.description)
    return [RowAdapter(r, keys) for r in rows]


class CursorAdapter:
    """Wraps a PyMySQL cursor to behave like sqlite3's cursor."""

    def __init__(self, pymysql_cursor):
        self._cur = pymysql_cursor

    @property
    def lastrowid(self):
        return self._cur.lastrowid

    @property
    def description(self):
        return self._cur.description

    def fetchall(self):
        return _rows_to_adapters(self._cur, self._cur.fetchall())

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        keys = tuple(d[0] for d in self._cur.description)
        return RowAdapter(row, keys)


class MySQLConnAdapter:
    """Wraps a PyMySQL connection to expose the same API as sqlite3.connect()."""

    def __init__(self, pymysql_conn):
        self._conn = pymysql_conn

    @staticmethod
    def _translate(sql: str) -> str:
        """Translate SQLite SQL to MySQL-compatible SQL.

        1. SQLite ? placeholders -> MySQL %s
        2. '%'||?||'%'  (LIKE concat)  -> CONCAT('%', %s, '%')
        3. datetime('now','localtime') -> NOW()
        """
        import re
        # Step 1: LIKE concat patterns before placeholder replacement
        # Pattern: '%'||?||'%'  (with optional spaces)
        sql = re.sub(r"'%'\s*\|\|\s*\?\s*\|\|\s*'%'", "CONCAT('%', %s, '%')", sql)
        # Step 2: datetime('now','localtime') or datetime('now')
        sql = re.sub(r"datetime\s*\(\s*'now'\s*(?:,\s*'[^']*')?\s*\)", "NOW()", sql,
                     flags=re.IGNORECASE)
        # Step 3: remaining ? -> %s (after the above so we don't double-convert)
        sql = sql.replace("?", "%s")
        return sql

    def execute(self, sql: str, params=()):
        sql = self._translate(sql)
        cur = self._conn.cursor()
        cur.execute(sql, params)
        return CursorAdapter(cur)

    def executemany(self, sql: str, seq_of_params):
        sql = self._translate(sql)
        cur = self._conn.cursor()
        cur.executemany(sql, seq_of_params)
        return CursorAdapter(cur)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    # Allow use as context manager (with conn:)
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_sqlite():
    """Return a connection-like object for the configured database.

    When DATABASE_URL is sqlite:///..., returns a real sqlite3.Connection
    (100% identical to the original behaviour).
    When DATABASE_URL is mysql://..., returns MySQLConnAdapter.
    """
    if _DB_SCHEME == "sqlite":
        conn = sqlite3.connect(_DB_CONFIG)
        conn.row_factory = sqlite3.Row
        return conn

    # MySQL path — lazy import so sqlite-only environments never need PyMySQL
    import pymysql
    import pymysql.cursors
    raw = pymysql.connect(**_DB_CONFIG, cursorclass=pymysql.cursors.Cursor)
    return MySQLConnAdapter(raw)


def run_migrations():
    """Apply incremental DDL migrations (ALTER TABLE etc.)."""
    conn = get_sqlite()
    try:
        conn.execute("ALTER TABLE erp_docs ADD COLUMN attachment TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        pass

    for col_sql in [
        "ALTER TABLE as_requests ADD COLUMN assigned_to INTEGER DEFAULT NULL",
        "ALTER TABLE as_requests ADD COLUMN assigned_name TEXT DEFAULT ''",
        "ALTER TABLE as_requests ADD COLUMN resolved_at TEXT DEFAULT ''",
        "ALTER TABLE as_requests ADD COLUMN admin_memo TEXT DEFAULT ''",
    ]:
        try:
            conn.execute(col_sql)
            conn.commit()
        except Exception:
            pass

    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS as_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            user_name TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )""")
        conn.commit()
    except Exception:
        pass

    for col_sql in [
        "ALTER TABLE erp_docs ADD COLUMN slip_type TEXT DEFAULT ''",
        "ALTER TABLE erp_docs ADD COLUMN slip_date TEXT DEFAULT ''",
        "ALTER TABLE erp_docs ADD COLUMN slip_total INTEGER DEFAULT 0",
    ]:
        try:
            conn.execute(col_sql)
            conn.commit()
        except Exception:
            pass

    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS slip_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            line_no INTEGER NOT NULL,
            account_name TEXT NOT NULL,
            debit INTEGER DEFAULT 0,
            credit INTEGER DEFAULT 0,
            partner TEXT DEFAULT '',
            summary TEXT DEFAULT ''
        )""")
        conn.commit()
    except Exception:
        pass

    conn.close()


def with_status_meta(rows):
    out = []
    for r in rows:
        d = dict(r)
        label, cls, style = STATUS_META.get(d.get("status", ""), (d.get("status", ""), "status-progress", ""))
        d["status_label"], d["status_class"], d["status_style"] = label, cls, style
        out.append(d)
    return out
