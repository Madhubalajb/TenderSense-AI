"""
verdict_detail.py — Bidder Verdict Detail Page
-------------------------------------------------
Shows the full criterion-by-criterion breakdown for a single bidder.
This is the most important page for officers — it's where they review
AI reasoning, see source evidence, and sign off on flagged items.

Layout:
  LEFT  — scrollable list of all criteria with Pass/Fail/Review status
  RIGHT — detail panel for the selected criterion:
            - Criterion text (from tender)
            - Evidence found (from bidder docs)
            - AI reasoning
            - Confidence breakdown bar
            - Officer action: Confirm Pass / Confirm Fail / Add note

This page is opened from evaluation.py when "Details →" is clicked.
"""

import time
import streamlit as st
from app.pipeline.verdict import apply_officer_override
from app.auth import get_current_user, log_event

VERDICT_STYLE = {
    "pass":   {"label": "Pass",         "color": "#059669", "bg": "#ECFDF5", "border": "#A7F3D0"},
    "fail":   {"label": "Fail",         "color": "#DC2626", "bg": "#FEF2F2", "border": "#FECACA"},
    "review": {"label": "Needs Review", "color": "#D97706", "bg": "#FFFBEB", "border": "#FDE68A"},
}

CATEGORY_LABEL = {
    "Financial":   "Financial",
    "Technical":   "Technical",
    "Compliance":  "Compliance",
    "Documentary": "Documentary",
}


def _badge(verdict):
    cfg = VERDICT_STYLE.get(verdict, {"label": verdict, "color": "#64748B", "bg": "#F8FAFC", "border": "#E2E8F0"})
    return (
        f'<span style="background:{cfg["bg"]};color:{cfg["color"]};'
        f'border:1px solid {cfg["border"]};padding:2px 9px;border-radius:10px;'
        f'font-size:11px;font-weight:500;">{cfg["label"]}</span>'
    )


def show():
    bidder_name  = st.session_state.get("selected_bidder")
    all_verdicts = st.session_state.get("all_verdicts", [])

    if not bidder_name or not all_verdicts:
        st.warning("No bidder selected. Go to Evaluation and click Details.")
        if st.button("Back to Evaluation"):
            st.session_state["page"] = "view_verdicts"
            st.rerun()
        st.stop()

    verdict = next((v for v in all_verdicts if v["bidder_name"] == bidder_name), None)
    if not verdict:
        st.error(f"Verdict data not found for: {bidder_name}")
        st.stop()

    officer = get_current_user().get("name", "Officer")
    results = verdict.get("criteria_results", [])

    # ── Page header ────────────────────────────────────────────────────────────
    col_back, col_title, col_badge = st.columns([1, 4, 1.5])

    with col_back:
        if st.button("Back to All Bidders"):
            st.session_state["selected_bidder"] = None
            st.session_state["page"]            = "view_verdicts"
            st.rerun()

    with col_title:
        st.title(bidder_name)
        st.caption(verdict.get("summary", ""))

    with col_badge:
        ov  = verdict["overall_verdict"]
        cfg = VERDICT_STYLE.get(ov, {})
        st.markdown(
            f'<div style="font-size:20px;font-weight:700;color:{cfg.get("color","#475569")};'
            f'margin-top:8px;">{cfg.get("label", ov).upper()}</div>'
            f'<div style="font-size:12px;color:#64748B;">Confidence: {verdict["overall_confidence"]:.0%}</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Criteria", verdict["total_criteria"])
    m2.metric("Passed",         verdict["passed"])
    m3.metric("Failed",         verdict["failed"])
    m4.metric("Review Needed",  verdict["review_needed"])
    st.divider()

    if "selected_criterion_idx" not in st.session_state:
        review_indices = [i for i, r in enumerate(results) if r["verdict"] == "review"]
        st.session_state["selected_criterion_idx"] = review_indices[0] if review_indices else 0

    selected_idx = st.session_state["selected_criterion_idx"]

    list_col, detail_col = st.columns([1, 1.8])

    # ════════════ LEFT: CRITERIA LIST ════════════
    with list_col:
        st.subheader("Criteria Checklist")

        ordered = (
            [r for r in results if r["verdict"] == "review"] +
            [r for r in results if r["verdict"] == "fail"] +
            [r for r in results if r["verdict"] == "pass"]
        )
        original_indices = {id(r): results.index(r) for r in ordered}

        for r in ordered:
            v_type     = r.get("verdict", "review")
            cfg        = VERDICT_STYLE.get(v_type, {})
            cid        = r.get("criterion_id", "")
            cat        = r.get("category", "")
            overridden = "officer_override" in r

            orig_idx    = original_indices[id(r)]
            is_selected = (orig_idx == selected_idx)

            verdict_dot = (
                f'<span style="display:inline-block;width:8px;height:8px;'
                f'border-radius:50%;background:{cfg.get("color","#94A3B8")};'
                f'margin-right:4px;vertical-align:middle;"></span>'
            )
            label = (
                f"[{cid}] {r.get('criterion_text','')[:50]}..."
                + (" (Overridden)" if overridden else "")
            )

            if st.button(
                label, key=f"crit_btn_{cid}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                st.session_state["selected_criterion_idx"] = orig_idx
                st.rerun()

            conf = r.get("confidence", 0.5)
            st.progress(conf, text=f"{conf:.0%} confidence")
            st.markdown("")

    # ════════════ RIGHT: DETAIL PANEL ════════════
    with detail_col:
        if selected_idx >= len(results):
            st.info("Select a criterion from the list.")
            st.stop()

        result = results[selected_idx]
        v_type = result.get("verdict", "review")
        cfg    = VERDICT_STYLE.get(v_type, {})
        cid    = result.get("criterion_id", "?")

        st.subheader(f"Criterion {cid} — {cfg.get('label', v_type)}")

        mandatory_text = "Mandatory" if result.get("mandatory") else "Optional"
        st.caption(
            f"{result.get('category', '')}  ·  {mandatory_text}  ·  "
            f"{result.get('section_reference', 'No section ref')}"
        )
        st.info(f"**Criterion (from tender):**\n\n{result.get('criterion_text', '')}")

        evidence = result.get("evidence", "No evidence found")
        if v_type == "pass":
            st.success(f"**Evidence found:**\n\n{evidence}")
        elif v_type == "fail":
            st.error(f"**Evidence / Gap:**\n\n{evidence}")
        else:
            st.warning(f"**Evidence (uncertain):**\n\n{evidence}")

        st.markdown("**AI Reasoning:**")
        st.markdown(f"> {result.get('reasoning', 'No reasoning available')}")

        layer = result.get("layer_used", "")
        method_label = {
            "numeric":  "Numeric comparison",
            "semantic": "Semantic matching",
            "llm":      "LLM reasoning",
            "none":     "Not evaluated",
        }.get(layer, layer)
        st.caption(f"Method: {method_label}")

        st.divider()
        st.markdown("**Confidence:**")
        conf = result.get("confidence", 0.5)
        st.progress(conf)
        st.caption(
            f"{conf:.0%} — " + (
                "High confidence" if conf >= 0.85 else
                "Medium confidence — review recommended" if conf >= 0.60 else
                "Low confidence — manual verification needed"
            )
        )

        # ── Override if already done ───────────────────────────────────────────
        if "officer_override" in result:
            ov_info = result["officer_override"]
            st.divider()
            st.success(
                f"Override recorded by {ov_info['officer']} at {ov_info['timestamp']}\n\n"
                f"Changed from **{ov_info['previous_verdict'].upper()}** to "
                f"**{ov_info['new_verdict'].upper()}**\n\n"
                f"Reason: _{ov_info['comment']}_"
            )
            if st.button("Undo Override", key=f"undo_{cid}"):
                del result["officer_override"]
                result["verdict"]      = ov_info["previous_verdict"]
                result["confidence"]   = 0.5
                result["needs_review"] = True
                log_event(
                    get_current_user().get("email", ""),
                    "override_undone", f"Override undone for {cid}"
                )
                st.rerun()

        # ── Officer action panel for review items ──────────────────────────────
        elif v_type == "review":
            st.divider()
            st.markdown("**Officer Review Required**")
            st.caption(
                "Review the criterion and evidence above, then record your decision. "
                "Your decision will be logged in the audit trail."
            )

            action_key = f"override_action_{cid}_{bidder_name}"
            action     = st.session_state.get(action_key)

            col_pass, col_fail = st.columns(2)
            with col_pass:
                if st.button("Mark as Pass", key=f"pass_btn_{cid}",
                             type="primary", use_container_width=True):
                    st.session_state[action_key] = "pass"
                    st.rerun()
            with col_fail:
                if st.button("Mark as Fail", key=f"fail_btn_{cid}",
                             use_container_width=True):
                    st.session_state[action_key] = "fail"
                    st.rerun()

            if action:
                action_label = "PASS" if action == "pass" else "FAIL"
                st.markdown(f"Recording verdict as: **{action_label}**")
                comment = st.text_area(
                    "Reason (required — recorded in audit trail):",
                    placeholder=(
                        "e.g. Certificate verified manually — valid until 2026. "
                        "OR: Experience period does not meet 3-year requirement."
                    ),
                    key=f"comment_input_{cid}", height=90,
                )
                confirm_col, cancel_col = st.columns(2)
                with confirm_col:
                    if st.button("Confirm & Save", key=f"confirm_btn_{cid}",
                                 type="primary", use_container_width=True):
                        if not comment.strip():
                            st.error("Please enter a reason before confirming.")
                        else:
                            for i, v in enumerate(all_verdicts):
                                if v["bidder_name"] == bidder_name:
                                    updated = apply_officer_override(
                                        v, cid, action, comment.strip(), officer
                                    )
                                    st.session_state["all_verdicts"][i] = updated
                                    break
                            log_event(
                                get_current_user().get("email", ""),
                                "officer_override",
                                f"Bidder: {bidder_name} | Criterion: {cid} | "
                                f"Verdict: {action} | Reason: {comment[:100]}"
                            )
                            _write_override_to_audit_file(
                                bidder_name, cid, action, comment, officer
                            )
                            del st.session_state[action_key]
                            st.success(f"Verdict for [{cid}] updated to {action.upper()}")
                            st.rerun()
                with cancel_col:
                    if st.button("Cancel", key=f"cancel_{cid}", use_container_width=True):
                        del st.session_state[action_key]
                        st.rerun()

        # ── Override for non-review items ──────────────────────────────────────
        else:
            with st.expander("Override AI Verdict (optional)"):
                st.caption(
                    "If you believe the AI verdict is incorrect, you can override it. "
                    "All overrides are logged."
                )
                override_to = st.selectbox(
                    "Change verdict to:",
                    ["pass", "fail", "review"],
                    index=["pass", "fail", "review"].index(v_type),
                    key=f"override_select_{cid}",
                )
                override_comment = st.text_area("Reason:", key=f"override_comment_{cid}", height=70)
                if st.button("Apply Override", key=f"apply_override_{cid}"):
                    if not override_comment.strip():
                        st.error("Please enter a reason.")
                    elif override_to == v_type:
                        st.info("Verdict unchanged.")
                    else:
                        for i, v in enumerate(all_verdicts):
                            if v["bidder_name"] == bidder_name:
                                updated = apply_officer_override(
                                    v, cid, override_to, override_comment.strip(), officer
                                )
                                st.session_state["all_verdicts"][i] = updated
                                break
                        log_event(
                            get_current_user().get("email", ""),
                            "officer_override",
                            f"Bidder: {bidder_name} | {cid} | {v_type}->{override_to}"
                        )
                        st.success(f"Verdict changed to {override_to.upper()}")
                        st.rerun()

        st.divider()
        prev_col, next_col = st.columns(2)
        with prev_col:
            if selected_idx > 0:
                if st.button("Previous", use_container_width=True):
                    st.session_state["selected_criterion_idx"] = selected_idx - 1
                    st.rerun()
        with next_col:
            if selected_idx < len(results) - 1:
                if st.button("Next", use_container_width=True, type="primary"):
                    st.session_state["selected_criterion_idx"] = selected_idx + 1
                    st.rerun()


def _write_override_to_audit_file(bidder, cid, verdict, comment, officer):
    import json, os
    os.makedirs("data/uploads", exist_ok=True)
    with open("data/uploads/audit_log.jsonl", "a") as f:
        f.write(json.dumps({
            "event": "officer_override", "bidder": bidder,
            "criterion_id": cid, "new_verdict": verdict,
            "comment": comment, "officer": officer,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }) + "\n")


if __name__ == "__main__":
    st.set_page_config(page_title="Tendra AI — Verdict Detail", layout="wide")
    show()