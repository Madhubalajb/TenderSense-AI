"""
db/models.py — Database Schema (plain SQLite, no ORM)
-------------------------------------------------------
All tables defined as CREATE TABLE SQL strings.
Uses Python's built-in sqlite3 — no SQLAlchemy dependency.

Tables:
  users         — officer accounts
  tenders       — uploaded tender documents
  criteria      — extracted eligibility criteria per tender
  bidders       — bidder names and documents per tender
  match_results — AI criterion-level results per bidder
  verdicts      — overall bidder verdict per tender
  audit_log     — immutable event log (every action)
"""

import os
import sqlite3
from contextlib import contextmanager

DB_PATH = "data/db/Tendra.db"


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row_factory set for dict-like access."""
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def db_session():
    """Context manager — commits on success, rolls back on error."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


CREATE_TABLES = [
    """CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        name          TEXT NOT NULL,
        email         TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role          TEXT NOT NULL DEFAULT 'officer',
        created_at    TEXT NOT NULL DEFAULT (datetime('now')),
        last_login    TEXT
    )""",

    """CREATE TABLE IF NOT EXISTS tenders (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        reference_no      TEXT,
        file_name         TEXT NOT NULL,
        extracted_text    TEXT,
        extraction_method TEXT,
        page_count        INTEGER,
        status            TEXT NOT NULL DEFAULT 'draft',
        created_by        TEXT NOT NULL,
        created_at        TEXT NOT NULL DEFAULT (datetime('now')),
        locked_at         TEXT,
        locked_by         TEXT
    )""",

    """CREATE TABLE IF NOT EXISTS criteria (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        tender_id         INTEGER NOT NULL,
        criterion_code    TEXT NOT NULL,
        criterion_text    TEXT NOT NULL,
        category          TEXT NOT NULL DEFAULT 'Compliance',
        mandatory         INTEGER NOT NULL DEFAULT 1,
        threshold_value   TEXT,
        threshold_unit    TEXT,
        years_required    INTEGER,
        section_reference TEXT,
        keywords          TEXT,
        added_manually    INTEGER NOT NULL DEFAULT 0,
        created_at        TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (tender_id) REFERENCES tenders(id)
    )""",

    """CREATE TABLE IF NOT EXISTS bidders (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        tender_id      INTEGER NOT NULL,
        name           TEXT NOT NULL,
        file_names     TEXT,
        extracted_text TEXT,
        added_by       TEXT,
        created_at     TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (tender_id) REFERENCES tenders(id)
    )""",

    """CREATE TABLE IF NOT EXISTS match_results (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        bidder_id        INTEGER NOT NULL,
        criterion_id     INTEGER NOT NULL,
        verdict          TEXT NOT NULL,
        confidence       REAL NOT NULL DEFAULT 0.5,
        evidence         TEXT,
        reasoning        TEXT,
        layer_used       TEXT,
        overridden       INTEGER NOT NULL DEFAULT 0,
        override_verdict TEXT,
        override_comment TEXT,
        override_by      TEXT,
        override_at      TEXT,
        created_at       TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (bidder_id)    REFERENCES bidders(id),
        FOREIGN KEY (criterion_id) REFERENCES criteria(id)
    )""",

    """CREATE TABLE IF NOT EXISTS verdicts (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        bidder_id          INTEGER NOT NULL UNIQUE,
        tender_id          INTEGER NOT NULL,
        overall_verdict    TEXT NOT NULL,
        overall_confidence REAL NOT NULL DEFAULT 0.0,
        total_criteria     INTEGER NOT NULL DEFAULT 0,
        passed             INTEGER NOT NULL DEFAULT 0,
        failed             INTEGER NOT NULL DEFAULT 0,
        review_needed      INTEGER NOT NULL DEFAULT 0,
        summary            TEXT,
        locked             INTEGER NOT NULL DEFAULT 0,
        locked_by          TEXT,
        locked_at          TEXT,
        created_at         TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (bidder_id) REFERENCES bidders(id),
        FOREIGN KEY (tender_id) REFERENCES tenders(id)
    )""",

    """CREATE TABLE IF NOT EXISTS audit_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email  TEXT,
        event_type  TEXT NOT NULL,
        entity_type TEXT,
        entity_id   INTEGER,
        detail      TEXT,
        timestamp   TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
]


def init_db():
    """Create all tables. Safe to call multiple times."""
    os.makedirs("data", exist_ok=True)
    conn = get_connection()
    for sql in CREATE_TABLES:
        conn.execute(sql)
    conn.commit()

    # Seed default admin if empty
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        import hashlib
        pw = hashlib.sha256("admin123".encode()).hexdigest()
        conn.execute(
            "INSERT INTO users (name,email,password_hash,role) VALUES (?,?,?,?)",
            ("Admin Officer", "admin@crpf.gov.in", pw, "admin"),
        )
        conn.commit()
        print("[db] Default admin: admin@crpf.gov.in / admin123")

    conn.close()


def row_to_dict(row) -> dict:
    return dict(row) if row else {}


def rows_to_list(rows) -> list:
    return [dict(r) for r in rows]