"""
db/queries.py — All Database Read/Write Operations
----------------------------------------------------
Every SQL query in the app lives here.
Pages and pipeline modules import from this file — no raw SQL elsewhere.
Returns plain Python dicts and lists (no ORM objects).

Usage:
  from app.db.queries import (
      save_tender, get_tender, save_criteria, get_criteria,
      save_bidder, save_match_results, save_verdict, get_all_verdicts
  )
"""

import json
import time
from typing import Optional

from app.db.models import get_connection, rows_to_list, row_to_dict


# ══════════════════════════════════════════════════════════════════════
#  USERS
# ══════════════════════════════════════════════════════════════════════

def get_user_by_email(email: str) -> Optional[dict]:
    conn = get_connection()
    row  = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email.lower(),)
    ).fetchone()
    conn.close()
    return row_to_dict(row)


def update_last_login(email: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE users SET last_login = ? WHERE email = ?",
        (time.strftime("%Y-%m-%d %H:%M:%S"), email.lower()),
    )
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════════
#  TENDERS
# ══════════════════════════════════════════════════════════════════════

def save_tender(
    file_name:         str,
    extracted_text:    str,
    extraction_method: str,
    created_by:        str,
    reference_no:      str = "",
    page_count:        int = None,
) -> int:
    """Insert a new tender record. Returns the new tender ID."""
    conn = get_connection()
    cur  = conn.execute(
        """INSERT INTO tenders
           (reference_no, file_name, extracted_text, extraction_method,
            page_count, status, created_by)
           VALUES (?, ?, ?, ?, ?, 'draft', ?)""",
        (reference_no, file_name, extracted_text,
         extraction_method, page_count, created_by),
    )
    tender_id = cur.lastrowid
    conn.commit()
    conn.close()
    return tender_id


def get_tender(tender_id: int) -> dict:
    conn = get_connection()
    row  = conn.execute(
        "SELECT * FROM tenders WHERE id = ?", (tender_id,)
    ).fetchone()
    conn.close()
    return row_to_dict(row)


def lock_tender(tender_id: int, locked_by: str) -> None:
    """Mark a tender's criteria as locked — no further editing allowed."""
    conn = get_connection()
    conn.execute(
        "UPDATE tenders SET status='locked', locked_at=?, locked_by=? WHERE id=?",
        (time.strftime("%Y-%m-%d %H:%M:%S"), locked_by, tender_id),
    )
    conn.commit()
    conn.close()


def get_all_tenders(user_email: str = None) -> list:
    """Return all tenders, optionally filtered by creator."""
    conn = get_connection()
    if user_email:
        rows = conn.execute(
            "SELECT id,reference_no,file_name,status,created_by,created_at "
            "FROM tenders WHERE created_by=? ORDER BY id DESC",
            (user_email,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id,reference_no,file_name,status,created_by,created_at "
            "FROM tenders ORDER BY id DESC"
        ).fetchall()
    conn.close()
    return rows_to_list(rows)


# ══════════════════════════════════════════════════════════════════════
#  CRITERIA
# ══════════════════════════════════════════════════════════════════════

def save_criteria(tender_id: int, criteria: list) -> list:
    """
    Insert all criteria for a tender. Deletes existing criteria first
    (safe to call again after officer edits).

    Args:
        tender_id: The tender these criteria belong to
        criteria:  List of criterion dicts from criteria_llm.py

    Returns:
        List of (criterion_code, db_id) tuples
    """
    conn = get_connection()

    # Clear existing criteria for this tender before re-saving
    conn.execute("DELETE FROM criteria WHERE tender_id = ?", (tender_id,))

    saved = []
    for c in criteria:
        keywords_json = json.dumps(c.get("keywords", []))
        cur = conn.execute(
            """INSERT INTO criteria
               (tender_id, criterion_code, criterion_text, category,
                mandatory, threshold_value, threshold_unit, years_required,
                section_reference, keywords, added_manually)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                tender_id,
                c.get("id", ""),
                c.get("criterion_text", ""),
                c.get("category", "Compliance"),
                1 if c.get("mandatory", True) else 0,
                c.get("threshold_value"),
                c.get("threshold_unit"),
                c.get("years_required"),
                c.get("section_reference"),
                keywords_json,
                1 if c.get("added_manually", False) else 0,
            ),
        )
        saved.append((c.get("id", ""), cur.lastrowid))

    conn.commit()
    conn.close()
    return saved


def get_criteria(tender_id: int) -> list:
    """Return all criteria for a tender as a list of dicts."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM criteria WHERE tender_id = ? ORDER BY id",
        (tender_id,),
    ).fetchall()
    conn.close()

    criteria = []
    for row in rows:
        c = dict(row)
        c["mandatory"] = bool(c["mandatory"])
        c["added_manually"] = bool(c["added_manually"])
        try:
            c["keywords"] = json.loads(c.get("keywords") or "[]")
        except Exception:
            c["keywords"] = []
        criteria.append(c)
    return criteria


# ══════════════════════════════════════════════════════════════════════
#  BIDDERS
# ══════════════════════════════════════════════════════════════════════

def save_bidder(
    tender_id:      int,
    name:           str,
    file_names:     list,
    extracted_text: str,
    added_by:       str,
) -> int:
    """Insert a bidder record. Returns the new bidder ID."""
    conn = get_connection()
    cur  = conn.execute(
        """INSERT INTO bidders
           (tender_id, name, file_names, extracted_text, added_by)
           VALUES (?, ?, ?, ?, ?)""",
        (tender_id, name, json.dumps(file_names), extracted_text, added_by),
    )
    bidder_id = cur.lastrowid
    conn.commit()
    conn.close()
    return bidder_id


def get_bidders(tender_id: int) -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM bidders WHERE tender_id = ? ORDER BY id",
        (tender_id,),
    ).fetchall()
    conn.close()
    bidders = []
    for row in rows:
        b = dict(row)
        try:
            b["file_names"] = json.loads(b.get("file_names") or "[]")
        except Exception:
            b["file_names"] = []
        bidders.append(b)
    return bidders


# ══════════════════════════════════════════════════════════════════════
#  MATCH RESULTS
# ══════════════════════════════════════════════════════════════════════

def save_match_results(bidder_id: int, results: list,
                        criterion_code_to_id: dict) -> None:
    """
    Save AI match results for one bidder.

    Args:
        bidder_id:            DB id of the bidder
        results:              List of match result dicts from matcher.py
        criterion_code_to_id: Maps criterion code (e.g. "C001") to its DB id
    """
    conn = get_connection()
    # Clear existing results for this bidder (safe to re-run)
    conn.execute("DELETE FROM match_results WHERE bidder_id = ?", (bidder_id,))

    for r in results:
        crit_code = r.get("criterion_id", "")
        crit_db_id = criterion_code_to_id.get(crit_code)
        if crit_db_id is None:
            continue

        conn.execute(
            """INSERT INTO match_results
               (bidder_id, criterion_id, verdict, confidence,
                evidence, reasoning, layer_used)
               VALUES (?,?,?,?,?,?,?)""",
            (
                bidder_id,
                crit_db_id,
                r.get("verdict", "review"),
                r.get("confidence", 0.5),
                r.get("evidence", ""),
                r.get("reasoning", ""),
                r.get("layer_used", ""),
            ),
        )
    conn.commit()
    conn.close()


def save_override(
    bidder_id:    int,
    criterion_id: int,
    new_verdict:  str,
    comment:      str,
    officer:      str,
) -> None:
    """Record an officer's override on a specific match result."""
    conn = get_connection()
    conn.execute(
        """UPDATE match_results
           SET overridden=1, override_verdict=?, override_comment=?,
               override_by=?, override_at=?
           WHERE bidder_id=? AND criterion_id=?""",
        (
            new_verdict, comment, officer,
            time.strftime("%Y-%m-%d %H:%M:%S"),
            bidder_id, criterion_id,
        ),
    )
    conn.commit()
    conn.close()


def get_match_results(bidder_id: int) -> list:
    """Return all match results for a bidder, joined with criterion data."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT mr.*, c.criterion_code, c.criterion_text,
                  c.category, c.mandatory, c.section_reference
           FROM match_results mr
           JOIN criteria c ON c.id = mr.criterion_id
           WHERE mr.bidder_id = ?
           ORDER BY c.id""",
        (bidder_id,),
    ).fetchall()
    conn.close()

    results = []
    for row in rows:
        r = dict(row)
        r["mandatory"] = bool(r["mandatory"])
        r["overridden"] = bool(r["overridden"])
        # Use effective verdict: override takes precedence
        if r["overridden"] and r.get("override_verdict"):
            r["effective_verdict"] = r["override_verdict"]
        else:
            r["effective_verdict"] = r["verdict"]
        results.append(r)
    return results


# ══════════════════════════════════════════════════════════════════════
#  VERDICTS
# ══════════════════════════════════════════════════════════════════════

def save_verdict(bidder_id: int, tender_id: int, verdict_dict: dict) -> None:
    """Insert or replace the overall verdict for a bidder."""
    conn = get_connection()
    conn.execute(
        """INSERT INTO verdicts
           (bidder_id, tender_id, overall_verdict, overall_confidence,
            total_criteria, passed, failed, review_needed, summary)
           VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(bidder_id) DO UPDATE SET
               overall_verdict=excluded.overall_verdict,
               overall_confidence=excluded.overall_confidence,
               total_criteria=excluded.total_criteria,
               passed=excluded.passed,
               failed=excluded.failed,
               review_needed=excluded.review_needed,
               summary=excluded.summary""",
        (
            bidder_id,
            tender_id,
            verdict_dict.get("overall_verdict", "review"),
            verdict_dict.get("overall_confidence", 0.5),
            verdict_dict.get("total_criteria", 0),
            verdict_dict.get("passed", 0),
            verdict_dict.get("failed", 0),
            verdict_dict.get("review_needed", 0),
            verdict_dict.get("summary", ""),
        ),
    )
    conn.commit()
    conn.close()


def get_all_verdicts(tender_id: int) -> list:
    """Return all verdicts for a tender, joined with bidder names."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT v.*, b.name AS bidder_name, b.file_names
           FROM verdicts v
           JOIN bidders b ON b.id = v.bidder_id
           WHERE v.tender_id = ?
           ORDER BY v.overall_verdict ASC, v.overall_confidence DESC""",
        (tender_id,),
    ).fetchall()
    conn.close()
    return rows_to_list(rows)


def lock_verdict(bidder_id: int, locked_by: str) -> None:
    """Lock a verdict — no further changes allowed."""
    conn = get_connection()
    conn.execute(
        "UPDATE verdicts SET locked=1, locked_by=?, locked_at=? WHERE bidder_id=?",
        (locked_by, time.strftime("%Y-%m-%d %H:%M:%S"), bidder_id),
    )
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════════
#  AUDIT LOG
# ══════════════════════════════════════════════════════════════════════

def get_audit_events(limit: int = 100, user_email: str = None) -> list:
    """Return recent audit events, optionally filtered by user."""
    conn = get_connection()
    if user_email:
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE user_email=? ORDER BY id DESC LIMIT ?",
            (user_email, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return rows_to_list(rows)