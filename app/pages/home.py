"""
home.py — Home Dashboard
--------------------------
The first page an officer sees after login.
Shows:
  - Active evaluation summary (if one is in progress)
  - Quick-start guide for new users
  - Recent audit activity
"""

import time
import streamlit as st
from app.auth import get_audit_log, get_current_user, log_event


def show():
    user = get_current_user()
    st.title(f"Welcome, {user.get('name', 'Officer')}")
    st.caption(time.strftime("Today is %A, %d %B %Y"))
    st.divider()

    tender_file = st.session_state.get("tender_filename")
    criteria    = st.session_state.get("criteria", [])
    verdicts    = st.session_state.get("all_verdicts", [])
    locked      = st.session_state.get("criteria_locked", False)

    if tender_file:
        st.subheader("Active Evaluation")
        with st.container():
            bc1, bc2, bc3, bc4 = st.columns(4)
            bc1.metric("Tender file",
                       tender_file[:22] + "..." if len(tender_file) > 22 else tender_file)
            bc2.metric("Criteria",      f"{len(criteria)} {'Locked' if locked else 'Unlocked'}")
            bc3.metric("Bidders added", len(st.session_state.get("bidders", {})))
            bc4.metric("Evaluated",     len(verdicts))

        st.markdown("<br>", unsafe_allow_html=True)

        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            if st.button("Tender Upload", use_container_width=True):
                st.session_state["page"] = "upload_tender"
                st.rerun()
        with col_b:
            if st.button("Bid Upload", use_container_width=True, disabled=not locked):
                st.session_state["page"] = "upload_bids"
                st.rerun()
        with col_c:
            if st.button("View Evaluation", use_container_width=True, disabled=not verdicts):
                st.session_state["page"] = "view_verdicts"
                st.rerun()
        with col_d:
            if st.button("Export Report", use_container_width=True, disabled=not verdicts):
                st.session_state["page"] = "export"
                st.rerun()

        if verdicts:
            st.divider()
            eligible   = sum(1 for v in verdicts if v["overall_verdict"] == "eligible")
            ineligible = sum(1 for v in verdicts if v["overall_verdict"] == "ineligible")
            review     = sum(1 for v in verdicts if v["overall_verdict"] == "review")
            s1, s2, s3 = st.columns(3)
            s1.metric("Eligible",     eligible)
            s2.metric("Ineligible",   ineligible)
            s3.metric("Needs Review", review)

        st.divider()
        if st.button("Start a New Evaluation  -  clears current session"):
            _clear_evaluation_session()
            st.success("Session cleared. Ready for a new tender.")
            st.rerun()

    else:
        st.subheader("Getting Started")
        st.markdown("No active evaluation. Follow these steps to evaluate a tender:")
        st.markdown("<br>", unsafe_allow_html=True)

        steps = [
            ("1", "Upload Tender Document",
             "Upload your NIT / tender PDF. The AI extracts all eligibility criteria automatically."),
            ("2", "Review & Lock Criteria",
             "Review the extracted criteria, edit if needed, then lock the list."),
            ("3", "Upload Bidder Documents",
             "Add each bidder and upload their documents - PDFs, certificates, and more."),
            ("4", "Run AI Evaluation",
             "AI matches each bidder's documents against the locked criteria."),
            ("5", "Review Verdicts",
             "See Pass / Fail / Review for every criterion. Action any flagged items."),
            ("6", "Export Report",
             "Download a CVC-ready PDF and Excel report with full audit trail."),
        ]

        icons = [
            "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
            "M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z",
            "M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z",
            "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",
            "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
            "M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
        ]

        for (num, title, desc), path in zip(steps, icons):
            st.markdown(
                f'<div style="display:flex;align-items:flex-start;gap:14px;'
                f'padding:12px 16px;margin-bottom:8px;background:#F8FAFC;'
                f'border:1px solid #E2E8F0;border-radius:8px;">'
                f'<div style="width:32px;height:32px;background:#0D9488;border-radius:6px;'
                f'display:flex;align-items:center;justify-content:center;flex-shrink:0;">'
                f'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" '
                f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                f'<path d="{path}"/></svg></div>'
                f'<div><div style="font-size:13px;font-weight:600;color:#1E293B;'
                f'font-family:\'Inter\',sans-serif;">Step {num}: {title}</div>'
                f'<div style="font-size:12px;color:#64748B;margin-top:2px;'
                f'font-family:\'Inter\',sans-serif;">{desc}</div></div></div>',
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Start — Upload a Tender Document", type="primary", use_container_width=True):
            st.session_state["page"] = "upload_tender"
            st.rerun()

    st.divider()
    st.subheader("Recent Activity")
    recent = get_audit_log(limit=10)
    if recent:
        event_labels = {
            "login":            "Signed in",
            "logout":           "Signed out",
            "register":         "Account created",
            "officer_override": "Verdict overridden",
            "report_exported":  "Report exported",
            "session_cleared":  "Session cleared",
            "criteria_locked":  "Criteria locked",
            "criteria_add":     "Criterion added",
            "criteria_remove":  "Criterion removed",
        }
        for entry in recent:
            label = event_labels.get(entry["event"], entry["event"])
            detail = f" — {entry['detail']}" if entry["detail"] else ""
            st.caption(f"`{entry['timestamp']}` &nbsp; {label} by {entry['user']}{detail}")
    else:
        st.caption("No activity recorded yet.")


def _clear_evaluation_session():
    keys_to_clear = [
        "tender_filename", "raw_tender_text", "criteria",
        "criteria_locked", "bidders", "evaluations",
        "all_verdicts", "selected_bidder", "current_step",
        "extraction_method",
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    log_event(
        get_current_user().get("email", ""),
        "session_cleared",
        "Evaluation session cleared by officer"
    )