"""
auth.py — Authentication
--------------------------
Simple email + password authentication using SQLite.
No external auth service needed — runs completely locally.

For the hackathon prototype this is intentionally simple.
In production you would use bcrypt password hashing and JWT tokens.

Tables:
  users(id, name, email, password_hash, role, created_at)

Roles:
  - officer : can upload tenders, upload bids, review, export
  - admin   : can also manage users and view all tenders
"""

import hashlib
import sqlite3
import time
import os

import streamlit as st

DB_PATH = "data/db/Tendra.db"


def init_db():
    os.makedirs("data", exist_ok=True)
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role          TEXT DEFAULT 'officer',
            created_at    TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            event      TEXT,
            detail     TEXT,
            timestamp  TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        _create_user(conn, "Admin Officer", "admin@crpf.gov.in", "admin123", "admin")
        #print("[auth] Default account: admin@crpf.gov.in / admin123")
    conn.close()


def _get_conn():
    os.makedirs("data", exist_ok=True)
    return sqlite3.connect(DB_PATH)


def _hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def _create_user(conn, name, email, password, role="officer"):
    conn.execute(
        "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
        (name, email, _hash_password(password), role)
    )
    conn.commit()


def register_user(name, email, password):
    if not name.strip() or not email.strip() or not password:
        return False, "All fields are required."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    if "@" not in email:
        return False, "Please enter a valid email address."
    conn = _get_conn()
    try:
        _create_user(conn, name.strip(), email.strip().lower(), password)
        log_event(email, "register", "New account created")
        return True, "Account created. Please sign in."
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists."
    finally:
        conn.close()


def login_user(email, password):
    conn  = _get_conn()
    email = email.strip().lower()
    user  = conn.execute(
        "SELECT id, name, email, role FROM users WHERE email=? AND password_hash=?",
        (email, _hash_password(password))
    ).fetchone()
    conn.close()
    if user:
        user_dict = {"id": user[0], "name": user[1], "email": user[2], "role": user[3]}
        log_event(email, "login", "Successful login")
        return True, user_dict
    return False, "Incorrect email or password."


def log_event(user_email, event, detail=""):
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO audit_log (user_email, event, detail) VALUES (?, ?, ?)",
            (user_email, event, detail)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[auth] Audit log error: {e}")


def get_audit_log(limit=100):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT user_email, event, detail, timestamp FROM audit_log ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [{"user": r[0], "event": r[1], "detail": r[2], "timestamp": r[3]} for r in rows]


def is_logged_in():
    return st.session_state.get("user") is not None


def get_current_user():
    return st.session_state.get("user", {})


def logout():
    user = get_current_user()
    if user:
        log_event(user.get("email", ""), "logout", "")
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def show_auth_page():
    # ── Page header ────────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    .auth-header { display:flex; align-items:center; gap:14px; margin-bottom:6px; }
    .auth-logo   { width:48px; height:48px; background:#0D9488; border-radius:10px;
                   display:flex; align-items:center; justify-content:center; flex-shrink:0; }
    .auth-title  { font-family:'Inter',sans-serif; font-size:28px; font-weight:600;
                   color:#0F172A; letter-spacing:-0.02em; }
    .auth-sub    { font-size:14px; color:#64748B; margin-bottom:4px; }
    .auth-tagline{ font-size:13px; color:#0D9488; font-style:italic;
                   border-left:2px solid #0D9488; padding-left:10px; }
    </style>
    <div class="auth-header">
      <div class="auth-logo">
        <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24"
             fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 14v3M12 14v3M16 14v3"/>
        </svg>
      </div>
      <div class="auth-title">Tendra AI</div>
    </div>
    <div class="auth-sub">Intelligent Tender Evaluation for a Transparent Bharat</div>
    <div class="auth-tagline">Turning paperwork into clarity - one tender at a time.</div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.divider()

    with st.sidebar:
        st.markdown("""
        <div style="padding:18px 14px 12px;border-bottom:1px solid rgba(255,255,255,0.07);">
          <div style="display:flex;align-items:center;gap:9px;margin-bottom:7px;">
            <div style="width:32px;height:32px;background:#0D9488;border-radius:6px;
                        display:flex;align-items:center;justify-content:center;">
              <svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24"
                   fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 14v3M12 14v3M16 14v3"/>
              </svg>
            </div>
            <span style="font-family:'Inter',sans-serif;font-size:17px;font-weight:600;color:#FFFFFF;">
              Tendra AI
            </span>
          </div>
          <div style="font-size:10px;color:#64748B;font-family:'Inter',sans-serif;">
            Sign in to access your evaluation workspace
          </div>
        </div>
        """, unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["Sign in", "Create account"])

    with tab_login:
        st.markdown("### Sign in to your account")
        with st.form("login_form"):
            email    = st.text_input("Email", placeholder="officer@crpf.gov.in")
            password = st.text_input("Password", type="password")
            submit   = st.form_submit_button("Sign in", type="primary", use_container_width=True)

        if submit:
            if not email or not password:
                st.error("Please enter your email and password.")
            else:
                success, result = login_user(email, password)
                if success:
                    st.session_state["user"]         = result
                    st.session_state["officer_name"] = result["name"]
                    st.success(f"Welcome back, {result['name']}.")
                    time.sleep(0.4)
                    st.rerun()
                else:
                    st.error(result)

        #st.caption("Default account: admin@crpf.gov.in / admin123")

    with tab_register:
        st.markdown("### Create a new account")
        with st.form("register_form"):
            name     = st.text_input("Full name", placeholder="Priya Sharma")
            email_r  = st.text_input("Official email", placeholder="officer@crpf.gov.in")
            pass_r   = st.text_input("Password (min 6 characters)", type="password")
            pass_r2  = st.text_input("Confirm password", type="password")
            submit_r = st.form_submit_button("Create account", use_container_width=True)

        if submit_r:
            if pass_r != pass_r2:
                st.error("Passwords do not match.")
            else:
                success, msg = register_user(name, email_r, pass_r)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)