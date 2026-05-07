"""
criteria_review.py — Criteria Review & AI Chatbot
"""

import json
import os
import time
import streamlit as st
from app.auth import get_current_user, log_event
from groq import Groq

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL   = "llama-3.3-70b-versatile"


def _get_client():
    key = GROQ_API_KEY or os.environ.get("GROQ_API_KEY", "")
    if not key:
        raise ValueError("GROQ_API_KEY not set.")
    return Groq(api_key=key)


def _ask_chatbot(user_question, criteria, chat_history):
    criteria_summary = "\n".join([
        f"- [{c['id']}] [{c['category']}] {'MANDATORY' if c['mandatory'] else 'Optional'}: "
        f"{c['criterion_text'][:120]}"
        for c in criteria
    ])
    history_text = "\n".join([
        f"{msg['role'].upper()}: {msg['content']}"
        for msg in chat_history[-6:]
    ])
    prompt = f"""You are an expert assistant helping a government procurement officer
understand and refine eligibility criteria extracted from a tender document.

Criteria:
{criteria_summary}

Recent conversation:
{history_text}

Officer's question: {user_question}

Instructions:
- Answer in clear, plain language suitable for a government officer
- If the officer asks to ADD a criterion: ACTION:ADD | category | mandatory(yes/no) | criterion text
- If the officer asks to REMOVE a criterion: ACTION:REMOVE | criterion_id
- If the officer asks to EDIT a criterion: ACTION:EDIT | criterion_id | new text
- For all other questions, answer clearly and helpfully
- Keep answers concise (3–5 sentences max)
- Always refer to criteria by their ID (C001, C002 etc.)
"""
    try:
        client   = _get_client()
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3, max_tokens=400,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Assistant error: {str(e)}\nPlease check that GROQ_API_KEY is set correctly."


def _parse_action(response_text):
    if not response_text.upper().startswith("ACTION:"):
        return {"type": None}
    parts = [p.strip() for p in response_text.split("|")]
    action_type = parts[0].replace("ACTION:", "").strip().lower()
    if action_type == "add" and len(parts) >= 4:
        return {"type": "add", "category": parts[1],
                "mandatory": parts[2].lower() in ("yes", "true", "mandatory"), "text": parts[3]}
    elif action_type == "remove" and len(parts) >= 2:
        return {"type": "remove", "criterion_id": parts[1]}
    elif action_type == "edit" and len(parts) >= 3:
        return {"type": "edit", "criterion_id": parts[1], "new_text": parts[2]}
    return {"type": None}


def _apply_action(action, criteria, officer):
    if action["type"] == "add":
        new_id = f"C{len(criteria) + 1:03d}"
        criteria.append({
            "id": new_id, "criterion_text": action["text"],
            "category": action["category"], "mandatory": action["mandatory"],
            "threshold_value": None, "threshold_unit": None,
            "years_required": None, "section_reference": "Added via chatbot",
            "keywords": [],
        })
        log_event(officer, "criteria_add", f"Added via chatbot: {action['text'][:80]}")
        return criteria, f"Added new criterion [{new_id}]"
    elif action["type"] == "remove":
        cid = action["criterion_id"]
        original = len(criteria)
        criteria = [c for c in criteria if c["id"] != cid]
        if len(criteria) < original:
            log_event(officer, "criteria_remove", f"Removed {cid}")
            return criteria, f"Removed criterion [{cid}]"
        return criteria, f"Criterion [{cid}] not found"
    elif action["type"] == "edit":
        cid = action["criterion_id"]
        for c in criteria:
            if c["id"] == cid:
                old_text = c["criterion_text"]
                c["criterion_text"] = action["new_text"]
                log_event(officer, "criteria_edit",
                          f"Edited {cid}: '{old_text[:60]}' -> '{action['new_text'][:60]}'")
                return criteria, f"Updated criterion [{cid}]"
        return criteria, f"Criterion [{cid}] not found"
    return criteria, ""


def show():
    st.title("Criteria Review")
    st.caption(
        "Review the extracted criteria on the left. "
        "Use the AI assistant on the right to clarify, or ask it to add, edit, or remove criteria."
    )

    if "criteria" not in st.session_state or not st.session_state["criteria"]:
        st.warning("No criteria found. Please complete Tender Upload first.")
        st.stop()

    officer  = get_current_user().get("email", "officer")
    criteria = st.session_state["criteria"]
    locked   = st.session_state.get("criteria_locked", False)

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    left_col, right_col = st.columns([1.2, 1])

    # ════════════ LEFT: CRITERIA LIST ════════════
    with left_col:
        st.subheader(f"Criteria List — {len(criteria)} extracted")

        if locked:
            st.success("Criteria are locked. Click Unlock to make changes.")
            if st.button("Unlock Criteria"):
                st.session_state["criteria_locked"] = False
                log_event(officer, "criteria_unlocked", "Criteria unlocked for editing")
                st.rerun()

        m1, m2, m3, m4 = st.columns(4)
        cats = [c["category"] for c in criteria]
        m1.metric("Total",     len(criteria))
        m2.metric("Mandatory", sum(1 for c in criteria if c["mandatory"]))
        m3.metric("Financial", cats.count("Financial"))
        m4.metric("Technical", cats.count("Technical"))
        st.divider()

        cat_labels = {
            "Financial":   "Financial",
            "Technical":   "Technical",
            "Compliance":  "Compliance",
            "Documentary": "Documentary",
        }

        for category in ["Financial", "Technical", "Compliance", "Documentary"]:
            cat_criteria = [c for c in criteria if c["category"] == category]
            if not cat_criteria:
                continue

            st.markdown(
                f'<div style="font-size:11px;font-weight:600;color:#475569;'
                f'text-transform:uppercase;letter-spacing:0.07em;margin:8px 0 4px;">'
                f'{cat_labels[category]} ({len(cat_criteria)})</div>',
                unsafe_allow_html=True,
            )

            for c in cat_criteria:
                mandatory_badge = (
                    '<span style="background:#FEE2E2;color:#DC2626;font-size:10px;'
                    'padding:1px 7px;border-radius:8px;">Mandatory</span>'
                    if c["mandatory"] else
                    '<span style="background:#F1F5F9;color:#64748B;font-size:10px;'
                    'padding:1px 7px;border-radius:8px;">Optional</span>'
                )
                ref = c.get("section_reference", "")

                with st.expander(f"[{c['id']}] {c['criterion_text'][:65]}...", expanded=False):
                    if locked:
                        st.markdown(c["criterion_text"])
                        st.markdown(mandatory_badge, unsafe_allow_html=True)
                        if ref:
                            st.caption(f"Ref: {ref}")
                    else:
                        new_text = st.text_area(
                            "Criterion text", value=c["criterion_text"],
                            key=f"crit_text_{c['id']}", height=80,
                        )
                        ec1, ec2, ec3 = st.columns([2, 1.5, 0.5])
                        with ec1:
                            new_cat = st.selectbox(
                                "Category",
                                ["Financial", "Technical", "Compliance", "Documentary"],
                                index=["Financial", "Technical", "Compliance", "Documentary"]
                                      .index(c["category"]),
                                key=f"crit_cat_{c['id']}",
                            )
                        with ec2:
                            new_mand = st.checkbox(
                                "Mandatory", value=c["mandatory"],
                                key=f"crit_mand_{c['id']}",
                            )
                        with ec3:
                            if st.button("Remove", key=f"del_{c['id']}"):
                                st.session_state["criteria"] = [
                                    x for x in criteria if x["id"] != c["id"]
                                ]
                                log_event(officer, "criteria_remove", f"Deleted {c['id']}")
                                st.rerun()

                        if (new_text != c["criterion_text"] or
                                new_cat != c["category"] or new_mand != c["mandatory"]):
                            c["criterion_text"] = new_text
                            c["category"]       = new_cat
                            c["mandatory"]      = new_mand
                            log_event(officer, "criteria_edit", f"Edited {c['id']}")
                        if ref:
                            st.caption(f"Ref: {ref}")

            st.markdown("")

        if not locked:
            with st.expander("Add Criterion Manually"):
                new_text = st.text_area("Criterion text", key="manual_add_text", height=70)
                nc1, nc2 = st.columns(2)
                new_cat  = nc1.selectbox(
                    "Category",
                    ["Financial", "Technical", "Compliance", "Documentary"],
                    key="manual_add_cat",
                )
                new_mand = nc2.checkbox("Mandatory", value=True, key="manual_add_mand")
                if st.button("Add") and new_text.strip():
                    new_id = f"C{len(criteria) + 1:03d}"
                    st.session_state["criteria"].append({
                        "id": new_id, "criterion_text": new_text.strip(),
                        "category": new_cat, "mandatory": new_mand,
                        "threshold_value": None, "threshold_unit": None,
                        "years_required": None, "section_reference": "Added manually",
                        "keywords": [],
                    })
                    log_event(officer, "criteria_add", f"Manual add: {new_text[:60]}")
                    st.rerun()

        st.divider()

        if not locked:
            if st.button("Lock Criteria & Proceed to Bid Upload",
                         type="primary", use_container_width=True):
                st.session_state["criteria_locked"] = True
                st.session_state["current_step"]    = 2
                log_event(officer, "criteria_locked", f"Locked {len(criteria)} criteria")
                os.makedirs("data/uploads", exist_ok=True)
                with open("data/uploads/criteria_locked.json", "w") as f:
                    json.dump({
                        "criteria":  criteria,
                        "locked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "locked_by": officer,
                    }, f, indent=2)
                st.success(f"{len(criteria)} criteria locked. Proceed to Bid Upload.")
                st.rerun()

    # ════════════ RIGHT: CHATBOT ════════════
    with right_col:
        st.subheader("AI Assistant")
        st.caption("Ask questions about the criteria, or ask me to add, edit, or remove entries.")

        with st.expander("Example questions"):
            examples = [
                "Explain criterion C001 in simple terms",
                "Which criteria are financial requirements?",
                "Is there a criterion about GST registration?",
                "Add a criterion: bidder must be registered on GeM portal",
                "What documents does a bidder need for C002?",
                "Which criteria might small vendors (MSMEs) struggle with?",
            ]
            for ex in examples:
                if st.button(ex, key=f"ex_{ex[:20]}", use_container_width=True):
                    st.session_state["chat_input_prefill"] = ex

        chat_container = st.container(height=380)
        with chat_container:
            if not st.session_state["chat_history"]:
                st.caption('Ask a question, e.g. "Which criteria are mandatory?"')
            for msg in st.session_state["chat_history"]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    if msg.get("action_result"):
                        st.success(msg["action_result"])

        prefill    = st.session_state.pop("chat_input_prefill", "")
        user_input = st.chat_input("Ask about the criteria...")
        if not user_input and prefill:
            user_input = prefill

        if user_input:
            st.session_state["chat_history"].append({"role": "user", "content": user_input})
            with st.spinner("Thinking..."):
                response = _ask_chatbot(
                    user_input, st.session_state["criteria"],
                    st.session_state["chat_history"],
                )
            action        = _parse_action(response)
            action_result = ""
            if action["type"] and not locked:
                updated_criteria, action_result = _apply_action(
                    action, st.session_state["criteria"], officer,
                )
                st.session_state["criteria"] = updated_criteria
                response = "\n".join(
                    line for line in response.splitlines()
                    if not line.upper().startswith("ACTION:")
                ).strip()
            elif action["type"] and locked:
                action_result = "Criteria are locked. Unlock them first to make changes."
            st.session_state["chat_history"].append({
                "role": "assistant", "content": response, "action_result": action_result,
            })
            log_event(officer, "chatbot_query", user_input[:100])
            st.rerun()

        if st.session_state["chat_history"]:
            if st.button("Clear chat", use_container_width=True):
                st.session_state["chat_history"] = []
                st.rerun()


if __name__ == "__main__":
    st.set_page_config(page_title="Tendra AI — Review Criteria", layout="wide")
    show()