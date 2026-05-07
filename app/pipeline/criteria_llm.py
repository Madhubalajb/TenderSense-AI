"""
criteria_llm.py — Criterion Extraction with Multi-Provider Fallback
--------------------------------------------------------------------
Automatically tries providers in order until one works.
Configure as many or as few as you like — skips any with no key set.

Provider priority (best → fallback):
  1. Groq       — llama-3.3-70b-versatile — 100k TPD free   — console.groq.com/keys
  2. Gemini     — gemini-2.0-flash         — 1M TPD free     — aistudio.google.com/apikey
  3. Cerebras   — llama3.1-8b              — 1M TPD free     — cloud.cerebras.ai
  4. SambaNova  — llama-3.3-70b            — free + $5 credit — cloud.sambanova.ai

Add keys to your .env file in the project root:
  GROQ_API_KEY=gsk_...
  GEMINI_API_KEY=AIza...
  CEREBRAS_API_KEY=csk-...
  SAMBANOVA_API_KEY=...

Install: pip install groq google-genai cerebras-cloud-sdk openai python-dotenv
(SambaNova uses the openai SDK with a custom base_url)
"""

import json
import os
import re
import time

from dotenv import load_dotenv
load_dotenv()

# ── API Keys ───────────────────────────────────────────────────────────────────
GROQ_API_KEY      = os.environ.get("GROQ_API_KEY",      "")
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY",    "")
CEREBRAS_API_KEY  = os.environ.get("CEREBRAS_API_KEY",  "")
SAMBANOVA_API_KEY = os.environ.get("SAMBANOVA_API_KEY", "")

# ── Model names ────────────────────────────────────────────────────────────────
GROQ_MODEL      = "llama-3.3-70b-versatile"
GEMINI_MODEL    = "gemini-2.5-flash-lite"  # 15 RPM + 1000 RPD free (was 2.0-flash: 5 RPM ~200 RPD)
CEREBRAS_MODEL  = "llama3.1-8b"        # universally available on free tier
#                                        # upgrade to "gpt-oss-120b" if your account has access
SAMBANOVA_MODEL = "Meta-Llama-3.3-70B-Instruct"      # strong model, free tier + $5 credit

CHUNK_SIZE = 12000  # chars per chunk

# ── Prompt ─────────────────────────────────────────────────────────────────────
# Kept deliberately compact — the prompt is sent once per chunk, so every token
# saved here directly extends your free-tier daily quota.
# Unicode box-chars (━, •, emoji) each cost 2-3 tokens vs 1 for plain ASCII.
EXTRACTION_PROMPT = """You are an expert in Indian government procurement and tender evaluation.

This handles ALL Indian government tender types published on CPPP/eprocure.gov.in, GeM, state portals, Railways (IREPS), Defence, PSUs and other authorities:
- Works contracts: civil, electrical, mechanical, road, bridge, plumbing, HVAC, STP/ETP, horticulture, AMC/maintenance
- Supply/goods: weapons, equipment, vehicles, furniture, uniforms, medical devices, IT hardware, consumables, food
- Services: manpower/housekeeping, security, IT/software, consultancy, printing, laundry, catering, transport, pest control
- Turnkey/EPC: supply + erection + commissioning + maintenance bundled
- Rate contracts: long-term pricing for recurring supply of goods or services
- RFP/RFQ/EOI: proposals or expressions of interest for professional/consultancy/technology services
- Hiring/leasing: vehicle hiring, equipment rental, space/land leasing

TASK: Extract eligibility criteria from the tender text below.

MANDATORY VERIFICATION GATE — before extracting any clause, ask TWO questions:
1. "What physical document would a procurement officer examine to verify this?"
2. "Is this document submitted WITH the bid (before award), or only at a later stage (trial, delivery, execution)?"
If no specific document exists, OR if the document is only provided post-award/at trial stage, DO NOT extract it.

EXTRACT — officer can verify from documents submitted WITH the bid:
- Financial turnover: absolute (Rs. 200 Lakh) OR percentage-based (30% of estimated cost) → CA-certified balance sheet/audited accounts with UDIN
- Past works/supply experience: similar works in CRPF/CPWD/MES/PWD/State Govt — may use absolute value OR percentage of NIT cost (e.g. one work ≥80%, two works ≥60%, three works ≥40%) → Completion certificates issued by Executive Engineer or above
- Contractor registration: CPWD/MES/NBCC/BRO/State PWD in appropriate class for the tender amount → Registration certificate valid on bid submission date
- Registrations held now: GST, PAN, EPF, ESIC, MSME/Udyam, GeM registration
- Licenses held now: arms license to manufacture, trade license, electrical license (already obtained, not future)
- Local content/MII status: Class-I or Class-II local supplier → Make in India Certificate (MII)
- EMD/Bid Security: bank draft, banker's cheque, or bank guarantee submitted with bid (original in tender box)
- MSE/Startup status: Udyam certificate, DIPP/DPIIT startup certificate
- OEM/Authorized dealer status: Details of Manufacturer, authorization certificate from OEM
- Declarations submitted with bid: non-debarment affidavit, blacklisting certificate, Land Border Sharing Declaration, integrity pact, non-submission of fake documents certificate

DO NOT EXTRACT — document only provided post-award, at trial, or during execution:
- Product technical specifications (QR/TDs): caliber, weight, dimensions, firing mode — verified at STEC/Field Trial/PDI, NOT at bid stage
- Lab/test certificates for product specs: "OEM to provide NABL/accredited lab certificate" — provided at trial stage
- Performance/Security Guarantee/Deposit: deposited only AFTER contract award
- Post-award obligations: warranty execution, after-sales service, operational training to be conducted
- Schedule of Quantity/BOQ items: individual work items, material specs, approved makes/brands list
- Delivery/dispatch terms: "deliver at consignee location", packing/marking requirements
- Payment terms, liquidated damages, escalation, force majeure, termination, defect liability clauses
- Online submission procedural instructions: "must read all terms", "submit through CPP Portal", "use DSC"
- Post-award labour/compliance: Contract Labour Act, BOCW, minimum wages, EPFO/ESIC payments during work
- Execution restrictions: "shall not sublet", "shall not transfer", indemnity, "shall provide tools/plants"
- Vague unverifiable statements with no specific threshold: "bidder must have definite proof of similar works" (no value/quantity stated)

CONCRETE EXAMPLES — REJECT:
- "Intending Bidder must have definite proof of satisfactorily completed similar works of magnitude specified" -> REJECT (vague, no specific value/quantity, unverifiable)
- "OEM to provide certificate from NABL/International accredited lab" -> REJECT (trial stage only)
- "Contractor shall comply with Contract Labour Act 1970" -> REJECT (post-award obligation)
- "Performance Security Deposit 3% within 28 days of contract" -> REJECT (post-award)
- "No Running Account Bill shall be paid till labour licenses submitted" -> REJECT (payment condition)
- "Bidder must read all terms and submit through online portal" -> REJECT (procedural instruction)
- "Contractor shall not sublet the contract without written permission" -> REJECT (execution restriction)
- "Approved makes: cement — ACC/UltraTech/Ambuja" -> REJECT (material specification for execution)

CONCRETE EXAMPLES — EXTRACT:
- "Minimum average annual turnover at least 30% of estimate cost put to tender during last 3 years ending 31st March" -> EXTRACT | threshold_value="30", threshold_unit="Percentage of NIT cost" | evidence: CA-certified audited balance sheet last 3 years
- "One similar completed work costing not less than 80% of estimated cost put to tender in last 3 financial years in CRPF/CPWD/MES/NBCC/BRO/State PWD" -> EXTRACT | category=Technical | evidence: Completion certificate from Executive Engineer or above
- "EMD Rs. 17,600/- valid 180 days from date of opening in favour of DIG GC Bilaspur payable at SBI Main Branch Bilaspur" -> EXTRACT | evidence: Bank draft/BG submitted with bid
- "Copy of valid registration as Contractor with CPWD/MES/NBCC/BRO/State PWD in respective categories" -> EXTRACT | category=Compliance | evidence: Registration certificate valid on last date of submission
- "Copy of registration certificate of GST, EPF and ESIC" -> EXTRACT | category=Compliance | evidence: GST certificate, EPF registration, ESIC registration
- "Valid arms license to manufacture 9mm Polymer Based Pistol as per Arms Rule 2016" -> EXTRACT | evidence: Arms license certificate
- "Only Class-I or Class-II local supplier as per MII order 19/07/2024 eligible" -> EXTRACT | evidence: Make in India Certificate
- "Non-debarment/blacklisting affidavit on Rs.100 non-judicial stamp paper" -> EXTRACT | category=Documentary | evidence: Notarized affidavit submitted with bid

DEDUPLICATION: Same criterion in multiple sections (NIT notice + Schedule + Appendix-8 checklist) -> extract ONCE, keep the version with specific numbers/thresholds.

Output ONLY valid JSON, no markdown, no explanation:
{"criteria":[{"id":"C001","criterion_text":"full criterion text as stated in tender","category":"Financial","mandatory":true,"threshold_value":"200","threshold_unit":"INR Lakh","years_required":3,"section_reference":"Section 9","keywords":["turnover","annual turnover"],"evidence_type":"CA-certified turnover statement with UDIN number"}]}

category=Financial|Technical|Compliance|Documentary; mandatory=true only if shall/must/required/essential; null for inapplicable fields.

Tender text:
"""


# ══════════════════════════════════════════════════════════════════════════════
# Provider calls
# ══════════════════════════════════════════════════════════════════════════════

def _call_groq(prompt: str) -> str:
    from groq import Groq
    client   = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=4096,
    )
    return response.choices[0].message.content


def _call_gemini(prompt: str) -> str:
    from google import genai
    from google.genai import types
    client   = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=4096),
    )
    return response.text


def _call_cerebras(prompt: str) -> str:
    from cerebras.cloud.sdk import Cerebras
    client   = Cerebras(api_key=CEREBRAS_API_KEY)
    response = client.chat.completions.create(
        model=CEREBRAS_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=4096,
    )
    return response.choices[0].message.content


def _call_sambanova(prompt: str) -> str:
    # SambaNova is OpenAI-compatible — uses openai SDK with custom base_url
    from openai import OpenAI
    client   = OpenAI(
        api_key=SAMBANOVA_API_KEY,
        base_url="https://api.sambanova.ai/v1",
    )
    response = client.chat.completions.create(
        model=SAMBANOVA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=4096,
    )
    return response.choices[0].message.content


# Provider registry — ordered by preference
# Each entry: (display_name, key_getter_fn, call_fn)
_PROVIDERS = [
    ("Groq",      lambda: GROQ_API_KEY,      _call_groq),
    ("Gemini",    lambda: GEMINI_API_KEY,    _call_gemini),
    ("Cerebras",  lambda: CEREBRAS_API_KEY,  _call_cerebras),
    ("SambaNova", lambda: SAMBANOVA_API_KEY, _call_sambanova),
]

# Keywords that indicate a rate-limit / quota error (not a hard error)
_RATE_LIMIT_SIGNALS = [
    "429", "rate limit", "quota", "resource_exhausted",
    "too many", "tokens per day", "tpd", "rate_limit_exceeded",
    "requests per", "per minute",
]


def _call_llm_with_fallback(prompt: str) -> tuple:
    """
    Try each configured provider in order.
    Returns (raw_response_text, provider_name_used).
    Raises RuntimeError if all providers fail.
    """
    errors = []

    for name, get_key, call_fn in _PROVIDERS:
        if not get_key():
            continue

        try:
            raw = call_fn(prompt)
            if raw and raw.strip():
                return raw, name
            errors.append(f"{name}: empty response")

        except Exception as e:
            err_str = str(e)
            is_rate_limit = any(s in err_str.lower() for s in _RATE_LIMIT_SIGNALS)

            if is_rate_limit:
                print(f"[criteria_llm] ⚠ {name} rate limited — trying next provider...")
            else:
                print(f"[criteria_llm] ✗ {name} error: {err_str[:120]}")

            errors.append(f"{name}: {err_str[:120]}")

    raise RuntimeError(
        "All configured LLM providers failed or are rate-limited.\n"
        "Errors:\n" + "\n".join(f"  • {e}" for e in errors) + "\n\n"
        "Solutions:\n"
        "  • Wait ~1 hour for Groq/Gemini rate limits to reset\n"
        "  • Add SAMBANOVA_API_KEY to .env  → cloud.sambanova.ai  (free + $5 credit)\n"
        "  • Add CEREBRAS_API_KEY to .env   → cloud.cerebras.ai   (1M tokens/day free)\n"
        "  • Add GEMINI_API_KEY to .env     → aistudio.google.com/apikey\n"
        "  • Add GROQ_API_KEY to .env       → console.groq.com/keys"
    )


def _which_providers_configured() -> list:
    return [name for name, get_key, _ in _PROVIDERS if get_key()]


# ══════════════════════════════════════════════════════════════════════════════
# Main extraction
# ══════════════════════════════════════════════════════════════════════════════

def extract_criteria(tender_text: str, max_chunks: int = 5) -> dict:
    """
    Extract ONLY pre-bid verifiable eligibility criteria from a tender document.
    Processes the full document in chunks with automatic provider fallback.
    """
    result = {
        "criteria":         [],
        "warnings":         [],
        "chunks_processed": 0,
    }

    configured = _which_providers_configured()
    if not configured:
        result["warnings"].append(
            "No LLM provider configured. Add at least one key to your .env file:\n"
            "  GROQ_API_KEY     → console.groq.com/keys\n"
            "  GEMINI_API_KEY   → aistudio.google.com/apikey\n"
            "  CEREBRAS_API_KEY → cloud.cerebras.ai\n"
            "  SAMBANOVA_API_KEY → cloud.sambanova.ai"
        )
        return result

    print(f"[criteria_llm] Providers available: {', '.join(configured)}")

    if not tender_text or len(tender_text.strip()) < 50:
        result["warnings"].append("Tender text is too short to extract criteria from.")
        return result

    chunks = _split_into_chunks(tender_text, CHUNK_SIZE)
    total  = len(chunks)
    print(f"[criteria_llm] Document: {len(tender_text):,} chars → {total} chunks")

    if total > max_chunks:
        result["warnings"].append(
            f"Document has {total} chunks; processing first {max_chunks} only. "
            "Increase max_chunks if criteria seem to be missing."
        )
        chunks = chunks[:max_chunks]

    all_criteria    = []
    seen_texts      = set()
    active_provider = None

    for i, chunk in enumerate(chunks):
        print(f"[criteria_llm] Chunk {i+1}/{len(chunks)} ({len(chunk):,} chars)...")

        try:
            raw, provider_used = _call_llm_with_fallback(EXTRACTION_PROMPT + chunk)
            if provider_used != active_provider:
                print(f"[criteria_llm] ✓ Using: {provider_used}")
                active_provider = provider_used
        except RuntimeError as e:
            result["warnings"].append(str(e))
            print(f"[criteria_llm] ❌ All providers exhausted.")
            break

        new_criteria = _parse_response(raw)
        added = 0
        for criterion in new_criteria:
            key = criterion.get("criterion_text", "").strip().lower()[:100]
            if key and key not in seen_texts:
                seen_texts.add(key)
                all_criteria.append(criterion)
                added += 1

        print(f"[criteria_llm]   → {len(new_criteria)} found, {added} new "
              f"(running total: {len(all_criteria)})")
        result["chunks_processed"] += 1

        # Small delay to be polite to rate limits
        if i < len(chunks) - 1:
            time.sleep(2)

    all_criteria = _deduplicate_criteria(all_criteria)

    for idx, c in enumerate(all_criteria, start=1):
        c["id"] = f"C{idx:03d}"

    result["criteria"] = all_criteria

    if not all_criteria:
        result["warnings"].append(
            "No criteria extracted. Check your API keys and document readability."
        )
    else:
        print(f"[criteria_llm] ✅ Done — {len(all_criteria)} evaluable criteria "
              f"(last provider: {active_provider})")

    return result


# ══════════════════════════════════════════════════════════════════════════════
# Parsing & deduplication
# ══════════════════════════════════════════════════════════════════════════════

def _parse_response(raw_text: str) -> list:
    cleaned    = re.sub(r"```(?:json)?", "", raw_text).strip()
    cleaned    = re.sub(r"```", "", cleaned).strip()
    json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)

    if not json_match:
        print(f"[criteria_llm] No JSON in response: {raw_text[:200]}")
        return []

    try:
        parsed   = json.loads(json_match.group(0))
        criteria = parsed.get("criteria", [])
        valid    = []
        for c in criteria:
            if isinstance(c, dict) and c.get("criterion_text"):
                c.setdefault("category",         "Compliance")
                c.setdefault("mandatory",         True)
                c.setdefault("threshold_value",   None)
                c.setdefault("threshold_unit",    None)
                c.setdefault("years_required",    None)
                c.setdefault("section_reference", None)
                c.setdefault("keywords",          [])
                c.setdefault("evidence_type",     None)
                valid.append(c)
        return valid
    except json.JSONDecodeError as e:
        print(f"[criteria_llm] JSON parse error: {e}\n{json_match.group(0)[:300]}")
        return []


def _deduplicate_criteria(criteria: list) -> list:
    """Keep the more specific version when near-duplicates are found."""
    if not criteria:
        return criteria

    def specificity_score(c: dict) -> int:
        score = 0
        if c.get("threshold_value"):   score += 3
        if c.get("section_reference"): score += 2
        if c.get("years_required"):    score += 2
        if c.get("threshold_unit"):    score += 1
        if c.get("evidence_type"):     score += 1
        score += len(c.get("keywords", []))
        score += min(len(c.get("criterion_text", "")), 200) // 50
        return score

    kept    = []
    dropped = set()

    for i, c1 in enumerate(criteria):
        if i in dropped:
            continue
        kw1   = set(k.lower() for k in c1.get("keywords", []))
        cat1  = c1.get("category", "")
        text1 = c1.get("criterion_text", "").lower()

        for j, c2 in enumerate(criteria):
            if j <= i or j in dropped:
                continue
            kw2   = set(k.lower() for k in c2.get("keywords", []))
            cat2  = c2.get("category", "")
            text2 = c2.get("criterion_text", "").lower()

            shared_kw    = len(kw1 & kw2)
            is_substring = (text1[:80] in text2 or text2[:80] in text1)

            if cat1 == cat2 and (shared_kw >= 3 or is_substring):
                if specificity_score(c1) >= specificity_score(c2):
                    dropped.add(j)
                else:
                    dropped.add(i)
                    break

        if i not in dropped:
            kept.append(c1)

    removed = len(criteria) - len(kept)
    if removed > 0:
        print(f"[criteria_llm] Dedup removed {removed} duplicate/redundant criteria")
    return kept


# ══════════════════════════════════════════════════════════════════════════════
# Chunking with overlap
# ══════════════════════════════════════════════════════════════════════════════

def _split_into_chunks(text: str, chunk_size: int) -> list:
    """Split at paragraph boundaries with 500-char overlap between chunks."""
    paragraphs  = text.split("\n\n")
    chunks      = []
    current     = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)
        if current_len + para_len > chunk_size and current:
            chunks.append("\n\n".join(current))
            overlap     = []
            overlap_len = 0
            for p in reversed(current):
                if overlap_len + len(p) < 500:
                    overlap.insert(0, p)
                    overlap_len += len(p)
                else:
                    break
            current     = overlap + [para]
            current_len = sum(len(p) for p in current)
        else:
            current.append(para)
            current_len += para_len

    if current:
        chunks.append("\n\n".join(current))
    return chunks


# ══════════════════════════════════════════════════════════════════════════════
# Test runner
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    configured = _which_providers_configured()
    print(f"Configured providers: {configured or ['NONE — add keys to .env']}")

    if len(sys.argv) < 2:
        print("\nUsage:   python -m app.pipeline.criteria_llm <path-to-tender-pdf>")
        print("Example: python -m app.pipeline.criteria_llm data/uploads/NIT008-544.pdf")
        sys.exit(1)

    from app.pipeline.extractor import extract_text

    file_path  = sys.argv[1]
    print(f"Reading: {file_path}")
    extraction = extract_text(file_path)
    if extraction["error"]:
        print(f"ERROR reading file: {extraction['error']}")
        sys.exit(1)

    text = extraction["text"]
    print(f"Extracted {len(text):,} characters via {extraction['method']}\n")
    print("─" * 60)

    # In your test runs — faster, cheaper
    result = extract_criteria(text, max_chunks=5)
   
    # For the actual demo recording only
    #result = extract_criteria(text, max_chunks=10)

    cats = {}
    for c in result["criteria"]:
        cats.setdefault(c["category"], []).append(c)

    print(f"\n✅ Extracted {len(result['criteria'])} evaluable criteria:\n")
    for category, items in sorted(cats.items()):
        print(f"── {category} ({len(items)}) ──")
        for c in items:
            tag = "🔴" if c["mandatory"] else "⚪"
            print(f"  {tag} [{c['id']}] {c['criterion_text'][:120]}")
            if c.get("threshold_value"):
                print(f"       Threshold : {c['threshold_value']} {c.get('threshold_unit') or ''}")
            if c.get("evidence_type"):
                print(f"       Evidence  : {c['evidence_type']}")
            if c.get("section_reference"):
                print(f"       Section   : {c['section_reference']}")
        print()

    if result["warnings"]:
        print("⚠ Warnings:")
        for w in result["warnings"]:
            print(f"  {w}")