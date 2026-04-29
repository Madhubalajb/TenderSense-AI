# 🏛️ TenderSense AI
### Intelligent Tender Evaluation for Government Procurement
> **AI for Bharat Hackathon · CRPF Challenge · Round 1 Submission**

---

> *"Turning paperwork into clarity - one tender at a time."*

AI that reads tender documents and bids, checks every eligibility criterion, explains every verdict, and flags doubts for human review - making CRPF procurement faster, fairer, and fully auditable.

---

## 📋 Table of Contents
1. [The Problem](#1-the-problem)
2. [What TenderSense AI Does](#2-what-tendersense-ai-does)
3. [How It Solves Real Pain Points](#3-how-it-solves-real-pain-points)
4. [Technical Approach](#4-technical-approach)
5. [Architecture - Free & Open-Source Stack](#5-architecture--free--open-source-stack)
6. [Works Offline · Works in Indian Languages](#6-works-offline--works-in-indian-languages)
7. [What Makes This Different](#7-what-makes-this-different)
8. [Honest Limitations](#8-honest-limitations-responsible-ai)
9. [Risks & Mitigations](#9-risks--mitigations)
10. [Impact & Scalability](#10-impact--scalability)
11. [Round 2 Sprint Plan](#11-round-2-sprint-plan)

---

## 1. The Problem

> **A typical CRPF evaluation scenario:**
> 10 bid packages arrive. Each is 80–200 pages of legal text. The tender has 12 eligibility criteria. That's up to **120 manual checks**. One wrong call → CVC complaint, legal challenge, or tender cancellation.

The current manual process has three structural failures:

- 🔴 **Slow & inconsistent** - different officers interpret the same criterion differently; no documented precedent.
- 🔴 **Audit risk** - informal notes don't satisfy CVC (Central Vigilance Commission) or RTI(Transparency Audit) requirements.
- 🔴 **Unfair to small vendors** - MSMEs (Micro, Small, and Medium Enterprises) with valid credentials lose out due to non-standard document formatting.

---

## 2. What TenderSense AI Does

A **browser-based assistant** - no installation, no cloud dependency. Five simple steps:

| Step | Officer Does | System Delivers |
|------|-------------|-----------------|
| **1. Upload Tender** | Upload the tender PDF or scan | Structured list of all eligibility criteria in ~3 minutes |
| **2. Validate** | Review & approve the criteria list | Locked evaluation baseline - single source of truth |
| **3. Upload Bids** | Drop all bidder packages in one batch | Every document parsed; every criterion checked automatically |
| **4. View Dashboard** | Open the evaluation report | Pass / Fail / Review per criterion, per bidder - with reasons |
| **5. Export** | Sign off and download the report | PDF + Excel report with full, timestamped audit trail |

---

## 3. How It Solves Real Pain Points

| Pain Point | TenderSense AI Fix | Benefit |
|------------|-------------------|---------|
| 120+ manual checks | All checks automated simultaneously | ~75% less officer verification time |
| Inconsistent evaluation | Same logic applied identically every time | Zero cross-evaluator inconsistency |
| Weak audit trail | Every action logged automatically | CVC-ready report generated with one click |
| MSME disadvantage | Looks for substance, not just presentation | Fairer outcomes for smaller vendors |
| Regional language docs | Reads Hindi, Tamil, Telugu, Bengali & more | No vendor penalised for language |

---

## 4. Technical Approach

> 💡 **Built entirely with free, open-source tools. Runs on a basic local server - no paid APIs required.**

### Step 1 - Reading the Tender Document

- Uploaded tender converted to text using **Apache Tika** (free, open-source)
- For scanned tenders: **Tesseract OCR** with **OpenCV** image clean-up
- **Mistral-7B via Ollama** (runs locally, no API key) reads the text and extracts every eligibility criterion
  - Extracts: criterion type, mandatory/optional, threshold value, section reference
  - Handles criteria buried in legal prose, cross-references, and conditional clauses
- Officer reviews and approves the extracted criteria list before evaluation begins

### Step 2 - Parsing Bidder Documents

- All formats accepted: typed PDFs, scanned copies, Word files, Excel sheets, certificate photos
- **Tesseract OCR** + **OpenCV** handles scanned and low-quality pages
- **spaCy** framework (free) with a custom fine-tune finds key facts: turnover figures, certificate numbers, dates, GST numbers
  - Trained for Indian formats: ₹ lakh/crore amounts, FY 2021-22 notation, GST/PAN numbers
  - Generic tools miss these - this is built specifically for Indian government documents
- Confidence score recorded for every extraction - low confidence = automatic human review flag

### Step 3 - Matching & Verdicts

- **Numeric criteria** (e.g. turnover ≥ ₹2 Cr): direct comparison after normalising lakh/crore
- **Qualitative criteria** (e.g. "government supply experience"): semantic similarity using **sentence-transformers** (free, runs offline)
  - Understands that "Revenue from Operations" and "Annual Turnover" mean the same thing
  - Not keyword matching - looks for *meaning*, not exact words
- **Complex criteria**: Mistral-7B reasons step-by-step and shows its reasoning to the officer

| Verdict | Condition | Officer Action Needed? |
|---------|-----------|----------------------|
| ✅ **PASS** | Clearly meets criterion (confidence ≥ 85%) | No - but override always available |
| ❌ **FAIL** | Clearly does not meet criterion (confidence ≥ 85%) | No - but override always available |
| ⚠️ **NEEDS REVIEW** | Uncertain or ambiguous (confidence < 85%) | **Yes - mandatory before locking** |

### Step 4 - Explainability (Every Verdict Has a Source)

No verdict is ever just "Pass" or "Fail". Every result shows:
- Which criterion (with the tender section reference)
- What value was found (e.g. "Annual Turnover ₹3.4 Cr - Balance Sheet, Page 7")
- Why it passed or failed (plain language, one sentence)
- How confident the system is (shown visibly - never hidden)

> **Example verdict:**
> ```
> Criterion : Annual Turnover ≥ ₹2 Crore for 3 consecutive years  [Tender 4.2(iii)]
> Found     : FY21-22: ₹2.8 Cr | FY22-23: ₹3.4 Cr | FY23-24: ₹3.1 Cr  [Balance Sheet, pp. 7–8]
> Reason    : All three years exceed ₹2 Cr threshold. Auditor signature detected on each page.
> Verdict   : ✅ PASS  |  Confidence: 92%
> ```

### Step 5 - Human Review & Audit Trail

- Flagged items appear in a **Review Queue** - sorted by priority (mandatory criteria first)
- Officer sees the criterion, extracted evidence, and original document side-by-side
- Officer confirms or overrides - **mandatory criteria cannot be skipped**
- Every action (AI verdict, officer review, override) logged with timestamp and user ID
- Final report (PDF + Excel) includes full provenance - ready for CVC audit or RTI response

---

## 5. Architecture - Free & Open-Source Stack

| What It Does | Tool Used | Why This Tool |
|-------------|-----------|---------------|
| Document ingestion (all formats) | **Apache Tika** | Handles PDF, Word, Excel, images - free |
| OCR (scanned pages) | **Tesseract 5.0 + OpenCV** | Supports 15+ Indian scripts natively - free |
| LLM for extraction & reasoning | **Mistral-7B via Ollama** | Runs on a basic server - no API key needed |
| Indian-specific entity recognition | **spaCy + custom fine-tune** | Recognises ₹ lakh/crore, GST numbers, Indian FY format |
| Semantic matching | **sentence-transformers (MiniLM)** | Multilingual, runs on CPU, free |
| Regional language translation | **IndicTrans2 (AI4Bharat)** | Best Indic-English translation model - open-source |
| Multilingual understanding | **MuRIL (Google, free)** | Pre-trained on 17 Indian languages |
| Background job queue | **Celery + Redis** | Handles batch uploads without timeout |
| Web interface | **Streamlit** (prototype) / React + FastAPI (production) | Streamlit = fastest to build; React for full deployment |
| Database & audit log | **PostgreSQL** | Free, reliable, exportable to CSV |
| Report generation | **ReportLab + openpyxl** | Pure Python - no licence cost |

### Deployment Options

| Tier | Infrastructure | Use Case |
|------|---------------|----------|
| **Tier 1** - NIC MeghRaj | Docker Compose on NIC cloud VMs | HQ offices with LAN |
| **Tier 2** - Local Server | 32 GB RAM, 8-core CPU, Ubuntu (~₹3–4 lakh one-time) | District / field offices |
| **Tier 3** - Laptop | 16 GB RAM, quantised Mistral-7B | Remote committee sessions |

- ✅ No internet required for core evaluation functions
- ✅ Quantised Mistral-7B runs on 16 GB RAM - no GPU needed
- ✅ All models bundled in Docker image - no external downloads at runtime

---

## 6. Works Offline · Works in Indian Languages

### Offline & Low-Bandwidth
- Full evaluation works with **zero internet** - all AI models run locally
- **Celery queue** lets officers submit documents and collect results later - no live connection needed
- If a document is too blurry to read reliably, the system **flags it for manual review** rather than guessing
- Laptop tier available for field-office or evaluation committee use

### Regional Languages
- OCR supports **Hindi, Tamil, Telugu, Bengali, Marathi, Kannada** and more via Tesseract
- **IndicTrans2** translates regional-language documents for matching - officer always sees original text
- **MuRIL** allows direct Hindi-to-Hindi matching - no translation error for Hindi documents
- Low-confidence translations are **flagged visibly** - never silently passed into evaluation

---

## 7. What Makes This Different

| What Existing Tools Lack | What TenderSense AI Provides |
|--------------------------|------------------------------|
| Built for Western English docs - fail on ₹ lakh/crore, GST numbers, Indian FY formats | Custom NER trained specifically for Indian government documents |
| No source-level explanation - just a score or flag | Every verdict shows: exact document, page, extracted value, and plain-language reason |
| Require cloud connectivity and foreign data storage - not viable for CRPF | 100% on-premise, Docker-packaged, no external API calls |
| Human review is an afterthought | Human sign-off is the primary design - AI prepares, officer decides |

---

## 8. Honest Limitations (Responsible AI)

We are upfront about what the system cannot do:

- **Very low-quality scans** - OCR may not extract text reliably; these are flagged for manual review, not auto-failed
- **Certificate authenticity** - the system checks format, not genuineness; physical verification remains the officer's responsibility
- **Unusual clause structures** - novel legal language without training precedent may be missed; officer validation of the criteria list is the safeguard
- **No binding AI decisions** - every final verdict is an officer decision; the system only prepares, never adjudicates
- **Automation complacency** - UI actively prompts critical review; mandatory officer action on all flagged items

---

## 9. Risks & Mitigations

| Risk | How It's Handled |
|------|-----------------|
| OCR fails on blurry scans | Auto-routed to human review with plain explanation |
| LLM extracts wrong criterion | Officer validates criteria list before evaluation begins |
| Ambiguous tender language | Flagged for officer to interpret - not guessed at |
| Sensitive document security | On-premise only; no data leaves the office network |
| Officers resist the new tool | Designed as assistant, not replacement; 2-day onboarding in Hindi & English |
| Model becomes outdated | Quarterly retraining; version recorded in every audit report |

---

## 10. Impact & Scalability

- 📉 **CRPF scale** - ~75% fewer officer-hours on verification; hardware ROI within Year 1
- 🇮🇳 **National scale** - India processes 200,000+ central tenders annually; same stack adapts with minor config changes
- 🔍 **Corruption reduction** - criterion-level audit trail makes inconsistent evaluation visible and challengeable
- 🏪 **MSME inclusion** - semantic matching + regional language support levels the playing field for small vendors
- 🎯 **Policy fit** - Digital India (paperless), GEM portal integration (API-ready), Make in India (built on Indian open-source AI: IndicTrans2, MuRIL)

---

## 11. Round 2 Sprint Plan

> Five parallel workstreams · Daily integration checkpoint · All built with the free-tier stack above

| Workstream | What It Produces | Done When… | Biggest Risk |
|------------|-----------------|------------|--------------|
| **1. Ingestion & OCR** | Pipeline reads all sandbox formats | No format errors; confidence scores on all pages | Broken PDFs → Apache Tika fallback |
| **2. Criterion Extraction** | Criteria Matrix JSON for each sample tender | ≥85% criteria correct on 3+ tenders | LLM output malformed → constrained prompts |
| **3. Bidder Parsing & NER** | Entity records per bidder with confidence scores | ≥80% correct values; uncertain items flagged | Low-quality scans → auto-route to review |
| **4. Matching & Verdicts** | Verdict table per criterion per bidder | ≥80% accuracy; ambiguous → Review not wrong call | Over-flagging → calibrate threshold on sandbox |
| **5. UI & Audit Trail** | Browser UI: dashboard, review queue, report export | Upload-to-export in <10 min by non-technical user | Frontend overrun → Streamlit as fallback |

### ✅ What a Successful Round 2 Demo Looks Like

A simulated officer uploads **one CRPF tender + five bidder packages**. TenderSense AI produces a live Criteria Matrix, Evaluation Dashboard, and Review Queue.

The demo walks through two bidders:
- **Bidder A** (clearly eligible) - source-traced passing verdicts for every criterion
- **Bidder B** (borderline) - Review Queue surfaces flagged items; officer reviews source document and records decision

Ends with an **exported evaluation report** - real data, no mocks, under 10 minutes, followable by any non-technical procurement officer.

---

## Tech Stack Summary

```
Document Parsing   : Apache Tika · Tesseract 5.0 · OpenCV · spaCy
LLM / Reasoning    : Mistral-7B (Ollama) - runs locally, free
Semantic Matching  : sentence-transformers MiniLM - runs on CPU, free
Indian Languages   : IndicTrans2 (AI4Bharat) · MuRIL (Google) - both free
Backend            : FastAPI · Celery · Redis · PostgreSQL
Frontend           : Streamlit (prototype) / React (production)
Deployment         : Docker Compose · NIC MeghRaj / Local Server / Laptop
```

---

<div align="center">

**We build for Bharat - not for the benchmark.**

*TenderSense AI · AI for Bharat Hackathon*

</div>
