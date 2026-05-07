"""
main.py — Tendra AI Entry Point
--------------------------------------
Run this file to start the application:
  streamlit run app/main.py

This file:
  1. Initialises the database
  2. Shows the login page if not authenticated
  3. Renders the sidebar navigation
  4. Routes to the correct page based on navigation
"""

import sys
import os
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

st.set_page_config(
    page_title="Tendra AI",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from app.tendra_theme import (
    inject_theme, render_sidebar_header, render_active_nav,
    render_nav_item, render_disabled_nav, render_session_summary,
    render_user_block, sidebar_section,
)

inject_theme()

from app.auth import init_db, is_logged_in, show_auth_page, logout, get_current_user
from app.pages.home            import show as show_home
from app.pages.tender_upload   import show as show_tender_upload
from app.pages.criteria_review import show as show_criteria_review
from app.pages.bid_upload      import show as show_bid_upload
from app.pages.evaluation      import show as show_evaluation
from app.pages.verdict_detail  import show as show_verdict_detail
from app.pages.export          import show as show_export

init_db()

if not is_logged_in():
    show_auth_page()
    st.stop()

user = get_current_user()

with st.sidebar:
    render_sidebar_header()

    criteria_extracted = bool(st.session_state.get("criteria", []))
    criteria_locked    = st.session_state.get("criteria_locked", False)
    bids_evaluated     = bool(st.session_state.get("all_verdicts", []))

    sidebar_section("Evaluation Workflow")

    if "page" not in st.session_state:
        st.session_state["page"] = "home"

    current_page = st.session_state["page"]

    completed = {
        "home":            False,
        "upload_tender":   criteria_extracted,
        "criteria_review": criteria_locked,
        "upload_bids":     bids_evaluated,
        "view_verdicts":   bids_evaluated,
        "verdict_detail":  bids_evaluated,
        "export":          False,
    }

    steps = [
        ("home",            0, "Home",            True),
        ("upload_tender",   1, "Tender Upload",   True),
        ("criteria_review", 2, "Criteria Review", criteria_extracted),
        ("upload_bids",     3, "Bid Upload",       criteria_locked),
        ("view_verdicts",   4, "Evaluation",       bids_evaluated),
        ("verdict_detail",  5, "Verdict Detail",   bids_evaluated),
        ("export",          6, "Export",           bids_evaluated),
    ]

    for page_key, step_num, label, enabled in steps:
        if current_page == page_key:
            render_active_nav(label, step_num)
        elif enabled:
            render_nav_item(label, step_num, done=completed.get(page_key, False))
            if st.button(label, key="nav_" + page_key, use_container_width=True):
                st.session_state["page"] = page_key
                if page_key not in ("verdict_detail",):
                    st.session_state.pop("selected_bidder", None)
                st.rerun()
        else:
            render_disabled_nav(label, step_num)

    sidebar_section("Session")

    verdicts   = st.session_state.get("all_verdicts", [])
    eligible   = sum(1 for v in verdicts if v.get("overall_verdict") == "eligible")
    ineligible = sum(1 for v in verdicts if v.get("overall_verdict") == "ineligible")
    review     = sum(1 for v in verdicts if v.get("overall_verdict") == "review")

    render_session_summary(
        tender_filename = st.session_state.get("tender_filename"),
        num_criteria    = len(st.session_state.get("criteria", [])),
        criteria_locked = criteria_locked,
        eligible        = eligible,
        ineligible      = ineligible,
        review          = review,
    )

    render_user_block(
        name  = user.get("name", "Officer"),
        role  = user.get("role", "officer"),
        email = user.get("email", ""),
    )

    if st.button("Sign out", use_container_width=True):
        logout()
        st.rerun()

page = st.session_state.get("page", "home")

if page == "home":
    show_home()
elif page == "upload_tender":
    show_tender_upload()
elif page == "criteria_review":
    show_criteria_review()
elif page == "upload_bids":
    show_bid_upload()
elif page == "view_verdicts":
    show_evaluation()
elif page == "verdict_detail":
    show_verdict_detail()
elif page == "export":
    show_export()
else:
    st.error("Unknown page: " + page)