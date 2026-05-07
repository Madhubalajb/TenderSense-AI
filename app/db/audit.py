"""
db/audit.py — Audit Trail Writer
----------------------------------
Writes every significant action to two stores:
  1. SQLite audit_log table — structured, queryable
  2. JSONL flat file         — portable, human-readable, survives DB issues

Records are NEVER updated or deleted — append only.

Usage:
  from app.db.audit import log, get_recent_events
  log("criteria_locked", user_email="officer@crpf.gov.in", detail="12 criteria locked")
"""

import json
import os
import time
from typing import Optional

from app.db.models import get_connection

JSONL_PATH = "data/audit_log.jsonl"


# ── Event type constants ───────────────────────────────────────────────────────
# Use these strings everywhere to avoid typos

LOGIN              = "login"
LOGOUT             = "logout"
REGISTER           = "register"
TENDER_UPLOADED    = "tender_uploaded"
TEXT_EXTRACTED     = "text_extracted"
CRITERIA_EXTRACTED = "criteria_extracted"
CRITERIA_EDITED    = "criteria_edited"
CRITERIA_ADDED     = "criteria_added"
CRITERIA_DELETED   = "criteria_deleted"
CRITERIA_LOCKED    = "criteria_locked"
CHATBOT_QUERY      = "chatbot_query"
BIDS_UPLOADED      = "bids_uploaded"
EVALUATION_STARTED = "evaluation_started"
EVALUATION_DONE    = "evaluation_done"
OFFICER_OVERRIDE   = "officer_override"
REPORT_EXPORTED    = "report_exported"
EVALUATION_LOCKED  = "evaluation_locked"


def log(
    event_type:  str,
    user_email:  str  = "system",
    entity_type: str  = None,
    entity_id:   int  = None,
    detail:      str  = "",
) -> None:
    """
    Write one audit event to both SQLite and JSONL.

    Args:
        event_type:  One of the constants above (e.g. CRITERIA_LOCKED)
        user_email:  Email of the officer performing the action
        entity_type: What was acted on (e.g. "tender", "criterion", "bidder")
        entity_id:   Database ID of the entity
        detail:      Free-text description of the action
    """
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "timestamp":   timestamp,
        "user_email":  user_email,
        "event_type":  event_type,
        "entity_type": entity_type,
        "entity_id":   entity_id,
        "detail":      detail,
    }

    # ── Write to SQLite ────────────────────────────────────────────────────────
    try:
        conn = get_connection()
        conn.execute(
            """INSERT INTO audit_log
               (user_email, event_type, entity_type, entity_id, detail, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_email, event_type, entity_type, entity_id, detail, timestamp),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[audit] SQLite write error: {e}")

    # ── Write to JSONL ─────────────────────────────────────────────────────────
    try:
        os.makedirs("data", exist_ok=True)
        with open(JSONL_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[audit] JSONL write error: {e}")


def log_override(
    user_email:    str,
    bidder_name:   str,
    criterion_id:  str,
    old_verdict:   str,
    new_verdict:   str,
    comment:       str,
) -> None:
    """Convenience wrapper for officer override events."""
    detail = (
        f"Bidder: {bidder_name} | Criterion: {criterion_id} | "
        f"{old_verdict.upper()} → {new_verdict.upper()} | Comment: {comment}"
    )
    log(OFFICER_OVERRIDE, user_email=user_email,
        entity_type="criterion", detail=detail)


def log_export(user_email: str, format_type: str, tender_ref: str) -> None:
    """Convenience wrapper for report export events."""
    log(REPORT_EXPORTED, user_email=user_email,
        detail=f"Format: {format_type.upper()} | Tender: {tender_ref}")


def get_recent_events(limit: int = 50) -> list:
    """
    Fetch recent audit events from SQLite.
    Returns a list of dicts, newest first.
    """
    try:
        conn = get_connection()
        rows = conn.execute(
            """SELECT user_email, event_type, entity_type,
                      entity_id, detail, timestamp
               FROM audit_log
               ORDER BY id DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[audit] Read error: {e}")
        return []


def get_events_for_tender(tender_id: int) -> list:
    """Fetch all audit events related to a specific tender."""
    try:
        conn = get_connection()
        rows = conn.execute(
            """SELECT user_email, event_type, entity_type,
                      entity_id, detail, timestamp
               FROM audit_log
               WHERE entity_id = ? AND entity_type IN ('tender','criterion','bidder')
               ORDER BY id ASC""",
            (tender_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[audit] Read error: {e}")
        return []


def get_override_events() -> list:
    """Fetch all officer override events — used in the export report."""
    try:
        conn = get_connection()
        rows = conn.execute(
            """SELECT user_email, detail, timestamp
               FROM audit_log
               WHERE event_type = ?
               ORDER BY id DESC""",
            (OFFICER_OVERRIDE,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return []


def read_jsonl() -> list:
    """Read the full JSONL audit log as a list of dicts."""
    if not os.path.exists(JSONL_PATH):
        return []
    events = []
    with open(JSONL_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return events