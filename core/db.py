import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test.db")

STATUS_META = {
    "urgent":      ("긴급",  "status-urgent",   ""),
    "progress":    ("진행중", "status-progress", ""),
    "in_progress": ("진행중", "status-progress", ""),
    "wait":        ("대기",  "status-progress", "background-color:#e2e3e5; color:#383d41;"),
    "pending":     ("대기",  "status-progress", "background-color:#e2e3e5; color:#383d41;"),
    "draft":       ("대기",  "status-progress", "background-color:#e2e3e5; color:#383d41;"),
    "done":        ("완료",  "status-done",     ""),
    "approved":    ("완료",  "status-done",     ""),
    "resolved":    ("완료",  "status-done",     ""),
    "rejected":    ("반려",  "status-urgent",   ""),
}


def get_sqlite():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def with_status_meta(rows):
    out = []
    for r in rows:
        d = dict(r)
        label, cls, style = STATUS_META.get(d.get("status", ""), (d.get("status", ""), "status-progress", ""))
        d["status_label"], d["status_class"], d["status_style"] = label, cls, style
        out.append(d)
    return out
