"""
tender_upload.py — The Streamlit UI for Week 1
------------------------------------------------
This page is what the officer sees when they upload a tender document.

It ties together the full Week 1 pipeline:
  1. Officer uploads a file
  2. extractor.py reads the text (with OCR fallback if scanned)
  3. criteria_llm.py sends text to Llama 3.3 70B-Versatile → gets criteria list
  4. Officer reviews the criteria and can edit/delete/add
  5. Criteria are stored in session state ready for the next step

How to run this page:
  streamlit run app/main.py
  (it will be linked from the main navigation)

Or run it in isolation for testing:
  streamlit run app/pages/tender_upload.py
"""

import os
import json
import time
import tempfile
from pathlib import Path

import streamlit as st
from app.pipeline.extractor    import extract_text
from app.pipeline.criteria_llm import extract_criteria

if __name__ == "__main__":
    st.set_page_config(page_title="Tendra AI — Upload Tender", layout="wide")

ACCEPTED_TYPES = ["pdf", "docx", "doc", "jpg", "jpeg", "png", "tiff"]


def save_uploaded_file(uploaded_file):
    suffix = Path(uploaded_file.name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        return tmp.name


def render_criterion_card(criterion, index):
    with st.container():
        col1, col2, col3, col4 = st.columns([0.5, 3, 1.5, 0.5])
        with col1:
            st.markdown(f"**{criterion['id']}**")
        with col2:
            new_text = st.text_area(
                label="Criterion text", value=criterion["criterion_text"],
                height=80, key=f"text_{index}", label_visibility="collapsed",
            )
            criterion["criterion_text"] = new_text
        with col3:
            sub1, sub2 = st.columns(2)
            with sub1:
                new_cat = st.selectbox(
                    "Category",
                    ["Financial", "Technical", "Compliance", "Documentary"],
                    index=["Financial", "Technical", "Compliance", "Documentary"]
                          .index(criterion.get("category", "Compliance")),
                    key=f"cat_{index}",
                )
                criterion["category"] = new_cat
            with sub2:
                new_mandatory = st.checkbox(
                    "Mandatory", value=criterion.get("mandatory", True),
                    key=f"mand_{index}",
                )
                criterion["mandatory"] = new_mandatory
        with col4:
            if st.button("Remove", key=f"del_{index}", help="Remove this criterion"):
                return None
        if criterion.get("section_reference"):
            st.caption(f"Ref: {criterion['section_reference']}")
        st.divider()
    return criterion


def show():
    st.title("Tender Upload")
    st.caption("Upload your tender document. Tendra AI will read it and extract all eligibility criteria.")

    # ── Step progress bar ──────────────────────────────────────────────────────
    step_names = ["Upload Tender", "Review Criteria", "Upload Bids", "View Verdicts", "Export"]
    cols = st.columns(len(step_names))
    for i, (col, step) in enumerate(zip(cols, step_names)):
        with col:
            if i == 0:
                st.markdown(
                    f'<div style="font-size:12px;font-weight:600;color:#0D9488;'
                    f'border-bottom:2px solid #0D9488;padding-bottom:4px;">{step}</div>',
                    unsafe_allow_html=True,
                )
            elif i < st.session_state.get("current_step", 0):
                st.markdown(
                    f'<div style="font-size:12px;color:#059669;border-bottom:2px solid #A7F3D0;'
                    f'padding-bottom:4px;">{step}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div style="font-size:12px;color:#94A3B8;border-bottom:1px solid #E2E8F0;'
                    f'padding-bottom:4px;">{step}</div>',
                    unsafe_allow_html=True,
                )

    st.divider()

    left_col, right_col = st.columns([2, 1])

    with right_col:
        with st.expander("Tips for best results", expanded=True):
            st.markdown("""
**Supported file types:**
- PDF (typed or scanned)
- Word documents (.docx, .doc)
- Images (.jpg, .png, .tiff)

**For best accuracy:**
- Upload the full NIT tender document
- Scanned documents should be at least 200 DPI
- Hindi documents are supported via OCR

**What happens next:**
1. Text is extracted from your document
2. Llama 3.3 identifies all eligibility criteria
3. You review and approve before evaluation begins
""")

    with left_col:
        uploaded_file = st.file_uploader(
            "Drop your tender document here",
            type=ACCEPTED_TYPES,
            help="Supported: PDF, DOCX, JPG, PNG, TIFF",
        )

        if uploaded_file is not None:
            st.success(f"File received: {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")

            # ── Extract button ─────────────────────────────────────────────────
            st.markdown("""
            <style>
            div[data-testid="stButton"]:has(button[kind="primary"]) button {
                background-color: #0D9488 !important;
            }
            </style>
            """, unsafe_allow_html=True)

            if st.button("Extract Criteria from this Document",
                         type="primary", use_container_width=True):

                with st.status("Reading document...", expanded=True) as status:
                    st.write("Saving uploaded file...")
                    tmp_path = save_uploaded_file(uploaded_file)

                    st.write("Extracting text...")
                    extraction = extract_text(tmp_path)
                    os.unlink(tmp_path)

                    if extraction["error"]:
                        status.update(label="Extraction failed", state="error")
                        st.error(f"Could not read the document: {extraction['error']}")
                        st.stop()

                    for warning in extraction["warnings"]:
                        st.warning(warning)

                    extracted_text = extraction["text"]
                    method         = extraction["method"]
                    char_count     = len(extracted_text)

                    st.write(f"Text extracted via {method.upper()} — {char_count:,} characters")

                    if char_count < 200:
                        status.update(label="Very little text extracted", state="error")
                        st.error(
                            "The document has very little readable text. "
                            "If scanned, ensure the scan is clear and at least 200 DPI."
                        )
                        st.stop()

                    st.write("Sending to AI to extract eligibility criteria...")
                    st.caption("This takes 30–90 seconds depending on document length...")

                    criteria_result = extract_criteria(extracted_text)
                    for warning in criteria_result["warnings"]:
                        st.warning(warning)

                    criteria = criteria_result["criteria"]

                    if not criteria:
                        status.update(label="No criteria found", state="error")
                        st.error("No eligibility criteria were found in this document.")
                        st.stop()

                    st.session_state["raw_tender_text"]   = extracted_text
                    st.session_state["criteria"]          = criteria
                    st.session_state["tender_filename"]   = uploaded_file.name
                    st.session_state["extraction_method"] = method
                    st.session_state["current_step"]      = 1

                    status.update(
                        label=f"Done — {len(criteria)} criteria found",
                        state="complete", expanded=False,
                    )

    # ── Criteria review section ────────────────────────────────────────────────
    if "criteria" in st.session_state and st.session_state["criteria"]:
        criteria = st.session_state["criteria"]

        st.divider()
        st.subheader(f"Extracted Criteria — {len(criteria)} found")
        st.markdown(
            "Review the criteria below. Edit the text, change the category, toggle mandatory, "
            "or remove any row. When satisfied, click **Lock & Proceed**."
        )

        metric_cols = st.columns(4)
        categories      = [c["category"] for c in criteria]
        mandatory_count = sum(1 for c in criteria if c["mandatory"])
        metric_cols[0].metric("Total Criteria",  len(criteria))
        metric_cols[1].metric("Mandatory",        mandatory_count)
        metric_cols[2].metric("Optional",         len(criteria) - mandatory_count)
        metric_cols[3].metric("Financial",        sum(1 for c in categories if c == "Financial"))

        st.divider()

        header_cols = st.columns([0.5, 3, 1.5, 0.5])
        header_cols[0].markdown("**ID**")
        header_cols[1].markdown("**Criterion**")
        header_cols[2].markdown("**Category / Mandatory**")
        header_cols[3].markdown("**Del**")

        updated_criteria = []
        for i, criterion in enumerate(criteria):
            result = render_criterion_card(criterion.copy(), i)
            if result is not None:
                updated_criteria.append(result)

        st.session_state["criteria"] = updated_criteria

        with st.expander("Add a Criterion Manually"):
            new_text = st.text_area("Criterion text", height=80, key="new_criterion_text")
            new_cat  = st.selectbox(
                "Category",
                ["Financial", "Technical", "Compliance", "Documentary"],
                key="new_criterion_cat",
            )
            new_mand = st.checkbox("Mandatory", value=True, key="new_criterion_mand")

            if st.button("Add Criterion") and new_text.strip():
                new_id = f"C{len(st.session_state['criteria']) + 1:03d}"
                st.session_state["criteria"].append({
                    "id": new_id, "criterion_text": new_text.strip(),
                    "category": new_cat, "mandatory": new_mand,
                    "threshold_value": None, "threshold_unit": None,
                    "years_required": None, "section_reference": "Added manually",
                    "keywords": [],
                })
                st.rerun()

        st.divider()

        col_a, col_b = st.columns([3, 1])
        with col_b:
            # Lock button — amber/gold so it stands out from the teal primary
            st.markdown("""
            <style>
            .lock-btn > div > button {
                background-color: #B45309 !important;
                color: #fff !important;
                border: none !important;
                border-radius: 6px !important;
                font-weight: 500 !important;
            }
            .lock-btn > div > button:hover { background-color: #92400E !important; }
            </style>
            """, unsafe_allow_html=True)

            clicked = st.button(
                "Lock & Proceed",
                type="primary", use_container_width=True,
                key="lock_and_proceed",
            )
            if clicked:
                st.session_state["criteria_locked"] = True
                st.session_state["current_step"]    = 2
                st.success(
                    f"{len(updated_criteria)} criteria locked. "
                    "Proceed to Upload Bidder Documents."
                )
                audit_path = "data/uploads/criteria_locked.json"
                os.makedirs("data/uploads", exist_ok=True)
                with open(audit_path, "w") as f:
                    json.dump({
                        "tender_file": st.session_state.get("tender_filename"),
                        "criteria":    updated_criteria,
                        "locked_at":   time.strftime("%Y-%m-%d %H:%M:%S"),
                    }, f, indent=2)
                st.caption(f"Saved to: `{audit_path}`")

        with col_a:
            if st.session_state.get("criteria_locked"):
                st.info("Criteria are locked. Go to Bid Upload in the sidebar.")

        with st.expander("View Raw Extracted Text"):
            st.text_area(
                label="Raw text from document",
                value=st.session_state.get("raw_tender_text", ""),
                height=300, disabled=True,
            )


if __name__ == "__main__":
    show()