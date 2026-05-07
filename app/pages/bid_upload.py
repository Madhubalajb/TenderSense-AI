"""
bid_upload.py — Bidder Document Upload Page
---------------------------------------------
Allows officers to upload one or more bidder document packages.
Each bidder gets their own folder of documents (PDF, DOCX, images, certs).

After upload, runs the full evaluation pipeline:
  extractor → ner → matcher → verdict

Results are stored in session state and displayed on the evaluation page.
"""

import os
import time
import json
import tempfile
import zipfile
from pathlib import Path

import streamlit as st
from app.pipeline.extractor import extract_text
from app.pipeline.matcher   import match_all_criteria
from app.pipeline.verdict   import compute_bidder_verdict, compute_all_verdicts

ACCEPTED_TYPES = ["pdf", "docx", "doc", "jpg", "jpeg", "png", "tiff", "zip"]


def show():
    st.title("Bid Upload")
    st.caption("Upload documents for each bidder. PDF, Word, images, and ZIP bundles are supported.")

    if not st.session_state.get("criteria_locked"):
        st.warning(
            "Criteria must be locked before uploading bidder documents. "
            "Complete Tender Upload and lock the criteria list first."
        )
        st.stop()

    criteria = st.session_state.get("criteria", [])
    st.info(
        f"Evaluating against **{len(criteria)} locked criteria** "
        f"from {st.session_state.get('tender_filename', 'tender')}"
    )
    st.divider()

    if "bidders" not in st.session_state:
        st.session_state["bidders"] = {}
    if "evaluations" not in st.session_state:
        st.session_state["evaluations"] = {}
    if "bidder_form_key" not in st.session_state:
        st.session_state["bidder_form_key"] = 0

    form_key = st.session_state["bidder_form_key"]

    with st.expander("Add a Bidder", expanded=True):
        col1, col2 = st.columns([2, 1])
        with col1:
            bidder_name = st.text_input(
                "Bidder / Company name",
                placeholder="e.g. Sunrise Textiles Pvt Ltd",
                key=f"new_bidder_name_{form_key}",
            )
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)

        uploaded_files = st.file_uploader(
            "Upload documents for this bidder",
            type=ACCEPTED_TYPES,
            accept_multiple_files=True,
            key=f"new_bidder_files_{form_key}",
            help="Balance sheets, certificates, GST, PAN, experience letters, etc.",
        )

        if st.button("Add Bidder", type="primary",
                     disabled=not (bidder_name and uploaded_files)):
            if bidder_name in st.session_state["bidders"]:
                st.error(f"A bidder named '{bidder_name}' already exists. Use a unique name.")
            else:
                saved_paths = []
                for f in uploaded_files:
                    tmp = _save_temp_file(f)
                    saved_paths.append({"name": f.name, "path": tmp, "size_kb": f.size // 1024})
                st.session_state["bidders"][bidder_name] = {
                    "files": saved_paths, "added_at": time.strftime("%H:%M:%S"),
                }
                st.success(f"Added {bidder_name} with {len(saved_paths)} document(s)")
                st.session_state["bidder_form_key"] += 1
                st.rerun()

    bidders = st.session_state.get("bidders", {})

    if bidders:
        st.divider()
        st.subheader(f"Bidders Added: {len(bidders)}")

        for bname, bdata in bidders.items():
            evaluated = bname in st.session_state.get("evaluations", {})
            status    = "Evaluated" if evaluated else "Pending"
            status_color = "#059669" if evaluated else "#D97706"

            with st.expander(f"{status} — {bname}"):
                st.markdown(
                    f'<span style="background:{"#ECFDF5" if evaluated else "#FFFBEB"};'
                    f'color:{status_color};border:1px solid {"#A7F3D0" if evaluated else "#FDE68A"};'
                    f'padding:2px 9px;border-radius:10px;font-size:11px;font-weight:500;">'
                    f'{status}</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"**{len(bdata['files'])} file(s) uploaded:**")
                for f in bdata["files"]:
                    st.caption(f"{f['name']} ({f['size_kb']} KB)")
                if st.button(f"Remove {bname}", key=f"remove_{bname}"):
                    del st.session_state["bidders"][bname]
                    if bname in st.session_state.get("evaluations", {}):
                        del st.session_state["evaluations"][bname]
                    st.rerun()

    if bidders:
        st.divider()
        col_a, col_b = st.columns([3, 1])
        with col_b:
            # Run AI Evaluation — distinct color (indigo) so it reads as a major action
            st.markdown("""
            <style>
            .run-eval-btn > div > button {
                background-color: #4F46E5 !important;
                color: #fff !important;
                border: none !important;
                border-radius: 6px !important;
                font-weight: 500 !important;
            }
            .run-eval-btn > div > button:hover { background-color: #4338CA !important; }
            </style>
            """, unsafe_allow_html=True)
            run_eval = st.button(
                "Run AI Evaluation",
                type="primary",
                use_container_width=True,
                disabled=len(bidders) == 0,
            )
        with col_a:
            st.markdown(
                f"Ready to evaluate **{len(bidders)} bidder(s)** against "
                f"**{len(criteria)} criteria**. "
                "This may take 2–5 minutes depending on document size."
            )
        if run_eval:
            _run_evaluation(bidders, criteria)


def _run_evaluation(bidders, criteria):
    total_bidders = len(bidders)
    progress_bar  = st.progress(0, text="Starting evaluation...")
    status_box    = st.empty()
    all_match_results = {}

    for i, (bidder_name, bdata) in enumerate(bidders.items()):
        progress_bar.progress(
            i / total_bidders,
            text=f"Evaluating {bidder_name} ({i+1}/{total_bidders})"
        )
        with status_box.container():
            st.markdown(f"### Processing: {bidder_name}")
            all_text_parts = []
            extraction_log = []

            for file_info in bdata["files"]:
                st.write(f"Reading: {file_info['name']}...")
                if file_info["path"].endswith(".zip"):
                    zip_texts = _extract_zip(file_info["path"])
                    all_text_parts.extend(zip_texts)
                    extraction_log.append(
                        f"ZIP: {file_info['name']} — {len(zip_texts)} files extracted"
                    )
                else:
                    result = extract_text(file_info["path"])
                    if result["text"]:
                        all_text_parts.append(f"=== {file_info['name']} ===\n{result['text']}")
                    extraction_log.append(
                        f"{file_info['name']}: {result['method'].upper()} "
                        f"— {len(result['text'])} chars"
                    )
                    for w in result.get("warnings", []):
                        st.warning(f"{file_info['name']}: {w}")

            bidder_text = "\n\n".join(all_text_parts)

            if not bidder_text.strip():
                st.error(f"No text extracted from {bidder_name}'s documents. Skipping.")
                continue

            st.write(f"Extracted {len(bidder_text):,} characters from {len(bdata['files'])} file(s)")
            st.write(f"Matching {len(criteria)} criteria...")

            match_results = match_all_criteria(criteria, bidder_text, bidder_name)
            all_match_results[bidder_name] = match_results

            passes  = sum(1 for r in match_results if r["verdict"] == "pass")
            fails   = sum(1 for r in match_results if r["verdict"] == "fail")
            reviews = sum(1 for r in match_results if r["verdict"] == "review")
            st.write(f"Complete: {passes} Pass  |  {fails} Fail  |  {reviews} Review")

    progress_bar.progress(1.0, text="Evaluation complete!")

    all_verdicts = []
    for bidder_name, match_results in all_match_results.items():
        verdict = compute_bidder_verdict(criteria, match_results, bidder_name)
        all_verdicts.append(verdict)

    st.session_state["evaluations"]  = all_match_results
    st.session_state["all_verdicts"] = all_verdicts
    st.session_state["current_step"] = 3

    _save_evaluation_to_disk(all_verdicts)
    status_box.empty()

    st.success(
        f"Evaluation complete — {len(all_verdicts)} bidder(s) evaluated. "
        "Navigate to Evaluation in the sidebar to see results."
    )

    eligible   = sum(1 for v in all_verdicts if v["overall_verdict"] == "eligible")
    ineligible = sum(1 for v in all_verdicts if v["overall_verdict"] == "ineligible")
    review     = sum(1 for v in all_verdicts if v["overall_verdict"] == "review")

    col1, col2, col3 = st.columns(3)
    col1.metric("Eligible",     eligible)
    col2.metric("Ineligible",   ineligible)
    col3.metric("Needs Review", review)

    st.rerun()


def _extract_zip(zip_path):
    texts = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            if name.startswith("__MACOSX") or name.endswith("/"):
                continue
            ext = Path(name).suffix.lower()
            if ext not in {".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".tiff"}:
                continue
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(zf.read(name))
                tmp_path = tmp.name
            result = extract_text(tmp_path)
            os.unlink(tmp_path)
            if result["text"]:
                texts.append(f"=== {name} ===\n{result['text']}")
    return texts


def _save_temp_file(uploaded_file):
    suffix = Path(uploaded_file.name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        return tmp.name


def _save_evaluation_to_disk(all_verdicts):
    os.makedirs("data/uploads", exist_ok=True)
    output_path = "data/uploads/evaluation_results.json"
    serialisable = []
    for v in all_verdicts:
        serialisable.append({
            "bidder_name":        v["bidder_name"],
            "overall_verdict":    v["overall_verdict"],
            "overall_confidence": v["overall_confidence"],
            "passed":             v["passed"],
            "failed":             v["failed"],
            "review_needed":      v["review_needed"],
            "summary":            v["summary"],
            "criteria_results":   v["criteria_results"],
            "evaluated_at":       time.strftime("%Y-%m-%d %H:%M:%S"),
        })
    with open(output_path, "w") as f:
        json.dump(serialisable, f, indent=2, default=str)
    print(f"[bid_upload] Saved to {output_path}")


if __name__ == "__main__":
    st.set_page_config(page_title="Tendra AI — Upload Bids", layout="wide")
    show()