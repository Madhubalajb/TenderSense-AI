"""
evaluation.py — Verdict Dashboard Page
----------------------------------------
Shows the full evaluation results:
  - Summary metrics at the top
  - Bidder-by-bidder verdict table
  - Click into any bidder to see criterion-level detail
  - Officer review panel for flagged criteria
  - Override controls with comment box
"""

import time
import streamlit as st
from app.pipeline.verdict import apply_officer_override

VERDICT_CONFIG = {
    "eligible":   {"label": "Eligible",      "color": "#059669", "bg": "#ECFDF5", "border": "#A7F3D0"},
    "ineligible": {"label": "Ineligible",    "color": "#DC2626", "bg": "#FEF2F2", "border": "#FECACA"},
    "review":     {"label": "Needs Review",  "color": "#D97706", "bg": "#FFFBEB", "border": "#FDE68A"},
    "pass":       {"label": "Pass",          "color": "#059669", "bg": "#ECFDF5", "border": "#A7F3D0"},
    "fail":       {"label": "Fail",          "color": "#DC2626", "bg": "#FEF2F2", "border": "#FECACA"},
}


def _badge(verdict):
    cfg = VERDICT_CONFIG.get(verdict, {"label": verdict, "color": "#64748B", "bg": "#F8FAFC", "border": "#E2E8F0"})
    return (
        f'<span style="background:{cfg["bg"]};color:{cfg["color"]};'
        f'border:1px solid {cfg["border"]};padding:2px 9px;border-radius:10px;'
        f'font-size:11px;font-weight:500;">{cfg["label"]}</span>'
    )


def show():
    st.title("Evaluation")

    all_verdicts = st.session_state.get("all_verdicts", [])
    if not all_verdicts:
        st.warning("No evaluation results yet. Complete Bid Upload first.")
        st.stop()

    eligible   = sum(1 for v in all_verdicts if v["overall_verdict"] == "eligible")
    ineligible = sum(1 for v in all_verdicts if v["overall_verdict"] == "ineligible")
    review     = sum(1 for v in all_verdicts if v["overall_verdict"] == "review")
    total      = len(all_verdicts)
    avg_conf   = sum(v["overall_confidence"] for v in all_verdicts) / total

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Bidders",  total)
    m2.metric("Eligible",       eligible)
    m3.metric("Ineligible",     ineligible)
    m4.metric("Needs Review",   review)

    st.caption(f"Average AI confidence: {avg_conf:.0%}")
    st.divider()

    selected_bidder = st.session_state.get("selected_bidder")
    if selected_bidder:
        _show_bidder_detail(selected_bidder, all_verdicts)
    else:
        _show_bidder_table(all_verdicts)


def _show_bidder_table(all_verdicts):
    st.subheader("Bidder Evaluation Summary")
    st.caption("Click 'Details' to see criterion-by-criterion breakdown for any bidder.")

    for verdict in all_verdicts:
        bname   = verdict["bidder_name"]
        overall = verdict["overall_verdict"]
        cfg     = VERDICT_CONFIG.get(overall, {})
        conf    = verdict["overall_confidence"]

        with st.container():
            col1, col2, col3, col4, col5 = st.columns([3, 1.5, 2, 1.5, 1])

            with col1:
                st.markdown(f"**{bname}**")

            with col2:
                st.markdown(_badge(overall), unsafe_allow_html=True)

            with col3:
                passed  = verdict["passed"]
                failed  = verdict["failed"]
                reviews = verdict["review_needed"]
                total_c = verdict["total_criteria"]
                # Simple text-based indicator instead of colored dots
                st.markdown(
                    f'<div style="font-size:12px;color:#475569;">'
                    f'<span style="color:#059669;font-weight:500;">{passed} pass</span> &nbsp;'
                    f'<span style="color:#DC2626;font-weight:500;">{failed} fail</span> &nbsp;'
                    f'<span style="color:#D97706;font-weight:500;">{reviews} review</span>'
                    f'</div>'
                    f'<div style="font-size:10px;color:#94A3B8;margin-top:2px;">{passed}/{total_c} criteria passed</div>',
                    unsafe_allow_html=True,
                )

            with col4:
                st.markdown(
                    f'<div style="font-size:12px;color:#475569;">Confidence</div>'
                    f'<div style="font-size:14px;font-weight:600;color:#0F172A;">{conf:.0%}</div>',
                    unsafe_allow_html=True,
                )

            with col5:
                if st.button("Details", key=f"detail_{bname}"):
                    st.session_state["selected_bidder"] = bname
                    st.rerun()

            st.divider()


def _show_bidder_detail(bidder_name, all_verdicts):
    verdict = next((v for v in all_verdicts if v["bidder_name"] == bidder_name), None)
    if not verdict:
        st.error(f"No evaluation found for {bidder_name}")
        return

    if st.button("Back to all bidders"):
        st.session_state["selected_bidder"] = None
        st.rerun()

    st.divider()

    overall = verdict["overall_verdict"]
    cfg     = VERDICT_CONFIG.get(overall, {})
    conf    = verdict["overall_confidence"]

    col_name, col_verdict = st.columns([3, 1])
    with col_name:
        st.subheader(bidder_name)
        st.caption(verdict["summary"])
    with col_verdict:
        st.markdown(
            f'<div style="font-size:22px;font-weight:600;color:{cfg.get("color","#475569")}">'
            f'{cfg.get("label", overall)}</div>'
            f'<div style="font-size:12px;color:#64748B;">Confidence: {conf:.0%}</div>',
            unsafe_allow_html=True,
        )

    st.divider()
    st.subheader("Criterion-Level Results")
    st.caption("Green = Pass  |  Red = Fail  |  Amber = Needs Officer Review")

    criteria_results = verdict.get("criteria_results", [])
    review_items = [r for r in criteria_results if r["verdict"] == "review"]
    other_items  = [r for r in criteria_results if r["verdict"] != "review"]

    if review_items:
        st.markdown(
            '<div style="font-size:13px;font-weight:600;color:#D97706;margin:8px 0 4px;">'
            'Flagged for Review</div>',
            unsafe_allow_html=True,
        )
        for result in review_items:
            _render_criterion_row(result, bidder_name, verdict, all_verdicts, highlight=True)
        st.markdown(
            '<div style="font-size:13px;font-weight:600;color:#334155;margin:8px 0 4px;">'
            'Other Criteria</div>',
            unsafe_allow_html=True,
        )

    for result in other_items:
        _render_criterion_row(result, bidder_name, verdict, all_verdicts)


def _render_criterion_row(result, bidder_name, verdict, all_verdicts, highlight=False):
    cid        = result.get("criterion_id", "?")
    ctext      = result.get("criterion_text", "")
    category   = result.get("category", "")
    mandatory  = result.get("mandatory", True)
    v_type     = result.get("verdict", "review")
    conf       = result.get("confidence", 0.5)
    evidence   = result.get("evidence", "")
    reasoning  = result.get("reasoning", "")
    layer      = result.get("layer_used", "")
    overridden = "officer_override" in result

    cfg = VERDICT_CONFIG.get(v_type, {})
    mandatory_tag = "Mandatory" if mandatory else "Optional"

    row_label = (
        f'{cfg.get("label","?")}  [{cid}] — {ctext[:75]}{"..." if len(ctext) > 75 else ""}  '
        f'`{category}` `{mandatory_tag}`'
        + (" — Overridden" if overridden else "")
    )

    with st.expander(row_label, expanded=(v_type == "review")):
        d1, d2 = st.columns(2)

        with d1:
            st.markdown("**Criterion (from tender)**")
            st.info(ctext)
            st.markdown("**Evidence found in bidder documents**")
            if evidence:
                if v_type == "pass":
                    st.success(evidence)
                elif v_type == "fail":
                    st.error(evidence)
                else:
                    st.warning(evidence)
            else:
                st.caption("No evidence found")

        with d2:
            st.markdown("**AI Reasoning**")
            st.markdown(f"_{reasoning}_")
            conf_col, layer_col = st.columns(2)
            conf_col.metric("Confidence", f"{conf:.0%}")
            layer_col.metric("Method", layer.upper() if layer else "—")

            if overridden:
                ov = result["officer_override"]
                st.success(
                    f"Overridden by {ov['officer']} at {ov['timestamp']}: {ov['comment']}"
                )

        if v_type == "review" and not overridden:
            st.divider()
            st.markdown("**Officer Review Required**")
            st.caption("Review the criterion and evidence, then record your decision.")

            oc1, oc2, oc3 = st.columns([1, 1, 2])
            with oc1:
                if st.button("Mark as Pass", key=f"pass_{cid}_{bidder_name}", type="primary"):
                    st.session_state[f"override_action_{cid}"] = "pass"
                    st.rerun()
            with oc2:
                if st.button("Mark as Fail", key=f"fail_{cid}_{bidder_name}"):
                    st.session_state[f"override_action_{cid}"] = "fail"
                    st.rerun()

            action = st.session_state.get(f"override_action_{cid}")
            if action:
                comment = st.text_area(
                    "Reason for your decision (required):",
                    key=f"comment_{cid}_{bidder_name}",
                    placeholder="e.g. Certificate verified manually — valid until 2026",
                )
                if st.button("Confirm and Save", key=f"confirm_{cid}_{bidder_name}"):
                    if not comment.strip():
                        st.error("Please enter a reason before confirming.")
                    else:
                        _apply_override(bidder_name, cid, action, comment, all_verdicts)
                        del st.session_state[f"override_action_{cid}"]
                        st.success(f"Verdict updated to {action.upper()}")
                        st.rerun()


def _apply_override(bidder_name, criterion_id, new_verdict, comment, all_verdicts):
    officer_name = st.session_state.get("officer_name", "Officer")
    for i, verdict in enumerate(all_verdicts):
        if verdict["bidder_name"] == bidder_name:
            updated = apply_officer_override(
                verdict, criterion_id, new_verdict, comment, officer_name
            )
            st.session_state["all_verdicts"][i] = updated
            _log_override(bidder_name, criterion_id, new_verdict, comment, officer_name)
            break


def _log_override(bidder_name, criterion_id, verdict, comment, officer):
    import json, os
    os.makedirs("data/uploads", exist_ok=True)
    log_path = "data/uploads/audit_log.jsonl"
    entry = {
        "event": "officer_override", "bidder": bidder_name,
        "criterion_id": criterion_id, "new_verdict": verdict,
        "comment": comment, "officer": officer,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


if __name__ == "__main__":
    st.set_page_config(page_title="Tendra AI — Verdicts", layout="wide")
    show()