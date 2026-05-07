"""
matcher.py — Semantic Matching Engine
--------------------------------------
Matches extracted bidder facts against tender eligibility criteria.

Three-layer matching strategy:
  Layer 1 — Structured numeric matching
    For criteria with clear thresholds (turnover ≥ ₹2 Cr, experience ≥ 3 years).
    Direct comparison after normalisation. High confidence, fast.

  Layer 2 — Semantic similarity matching
    For qualitative criteria ("prior experience with government bodies").
    Uses sentence-transformers to compare meaning — not just keywords.
    Handles paraphrase: "Revenue from Operations" = "Annual Turnover".

  Layer 3 — LLM reasoning (for complex/ambiguous cases)
    When layers 1 and 2 are inconclusive, asks LLM to reason through it.
    Slowest but handles the hardest cases (conditional clauses, legal language).

Output:
  For each (criterion, bidder) pair:
    - verdict:     "pass" | "fail" | "review"
    - confidence:  0.0 – 1.0
    - evidence:    What was found in the bidder documents
    - reasoning:   Plain-language explanation
    - layer_used:  Which matching layer produced the verdict

Usage:
  from app.pipeline.matcher import match_criterion
  result = match_criterion(criterion, bidder_facts, bidder_text)
"""

import re
import json
import requests
from typing import Optional

# sentence-transformers for semantic similarity
# Downloads the model on first use (~90MB, cached after that)
from sentence_transformers import SentenceTransformer, util

# Our NER module
from app.pipeline.ner import extract_bidder_facts, extract_entities_by_type


# ── Load sentence-transformer model ───────────────────────────────────────────
# "paraphrase-MiniLM-L6-v2" is small (80MB), fast, runs on CPU,
# and handles multilingual text reasonably well.
# For better multilingual support, use "paraphrase-multilingual-MiniLM-L12-v2"
# (larger, ~120MB, supports Hindi and other Indian languages).

_embedding_model = None

def get_embedding_model():
    """Get the sentence-transformer model (loaded once, reused after that)."""
    global _embedding_model
    if _embedding_model is None:
        print("[matcher] Loading sentence-transformer model...")
        _embedding_model = SentenceTransformer("paraphrase-MiniLM-L6-v2")
        print("[matcher] Model loaded")
    return _embedding_model


# ── Ollama config (reused from criteria_llm.py) ───────────────────────────────
OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"

# Confidence thresholds
PASS_THRESHOLD   = 0.80   # ≥ 80%: auto-pass
FAIL_THRESHOLD   = 0.80   # ≥ 80% confident it fails: auto-fail
REVIEW_THRESHOLD = 0.60   # between 60-80%: flag for review


# ── Main matching function ─────────────────────────────────────────────────────

def match_criterion(criterion: dict, bidder_facts: dict,
                    bidder_text: str) -> dict:
    """
    Match a single criterion against a bidder's extracted facts and documents.
    
    Args:
        criterion:    One criterion dict from criteria_llm.py output
        bidder_facts: Structured facts from ner.extract_bidder_facts()
        bidder_text:  Full concatenated text of the bidder's documents
    
    Returns:
        {
          "criterion_id":  "C001",
          "verdict":       "pass" | "fail" | "review",
          "confidence":    0.92,
          "evidence":      "Annual Turnover FY 2023-24: ₹3.1 Cr (from Balance Sheet)",
          "reasoning":     "All three financial years exceed ₹2 Cr threshold",
          "layer_used":    "numeric" | "semantic" | "llm",
          "needs_review":  False,
        }
    """
    category = criterion.get("category", "Compliance")
    
    # ── Route to the appropriate matching strategy ─────────────────────────────
    if category == "Financial":
        result = _match_financial(criterion, bidder_facts, bidder_text)
    
    elif category == "Technical":
        result = _match_technical(criterion, bidder_facts, bidder_text)
    
    elif category == "Compliance":
        result = _match_compliance(criterion, bidder_facts, bidder_text)
    
    elif category == "Documentary":
        result = _match_documentary(criterion, bidder_facts, bidder_text)
    
    else:
        # Unknown category — use semantic matching
        result = _match_semantic(criterion, bidder_text)
    
    # Add standard fields
    result["criterion_id"] = criterion.get("id", "?")
    result["criterion_text"] = criterion.get("criterion_text", "")
    result["mandatory"]    = criterion.get("mandatory", True)
    result["needs_review"] = result["verdict"] == "review"
    
    return result


# ── Layer 1a: Financial criterion matching ─────────────────────────────────────

def _match_financial(criterion: dict, bidder_facts: dict,
                     bidder_text: str) -> dict:
    """
    Match financial criteria (turnover, net worth, etc.).
    
    Strategy:
      1. Extract the threshold from the criterion
      2. Deduplicate and sanitise turnover values from bidder facts
      3. Determine if the criterion is about AVERAGE or PER-YEAR threshold
      4. Check accordingly
    """
    criterion_text  = criterion.get("criterion_text", "").lower()
    threshold_value = criterion.get("threshold_value")
    years_required  = criterion.get("years_required")

    # Parse threshold value (e.g. "2 crore" → 2.0)
    threshold_crore = _parse_threshold_to_crore(threshold_value, criterion_text)

    # ── Deduplicate turnover entries by FY ─────────────────────────────────────
    # Keep only entries with a valid, non-zero value. When multiple entries
    # share the same FY (e.g. from different pages), keep the largest.
    raw_turnovers = bidder_facts.get("turnover_values", [])
    fy_best: dict = {}
    for t in raw_turnovers:
        v = t.get("value_crore")
        if v is None or v <= 0:
            continue
        # Skip implausibly large values (mis-parsed identifiers)
        if v > 10_000:
            continue
        fy = t.get("fy") or "unknown"
        if fy not in fy_best or v > fy_best[fy]["value_crore"]:
            fy_best[fy] = t

    turnovers = list(fy_best.values())

    if not turnovers:
        return {
            "verdict":    "review",
            "confidence": 0.5,
            "evidence":   "No valid turnover figures found in submitted documents",
            "reasoning":  "Could not locate financial figures in the documents. "
                          "This may be because the balance sheet was in a format "
                          "that could not be read, or financial data was not submitted.",
            "layer_used": "numeric",
        }

    evidence_parts = [
        f"FY {t['fy'] or 'unknown'}: ₹{t['value_crore']:.2f} Cr (from \"{t['original']}\")"
        for t in turnovers
    ]
    evidence = " | ".join(evidence_parts)

    # ── Detect "average" criterion ────────────────────────────────────────────
    # Criteria like "minimum average annual turnover of 30% of estimated cost
    # during the last 3 years" require checking the AVERAGE, not each year.
    is_average_criterion = bool(re.search(r"\baverage\b", criterion_text))

    if threshold_crore is not None:

        if is_average_criterion:
            # ── Average path ──────────────────────────────────────────────────
            # Use all FY-known entries for the average; fall back to all if none
            # have FY info.
            known = [t for t in turnovers if t.get("fy") and t["fy"] != "unknown"]
            pool  = known if known else turnovers

            # If years_required is specified, use only that many most-recent years
            n = int(years_required) if years_required else len(pool)
            # Sort by FY descending to pick the most recent years
            pool_sorted = sorted(
                pool,
                key=lambda t: t.get("fy") or "0000-00",
                reverse=True,
            )
            selected = pool_sorted[:n]

            avg = sum(t["value_crore"] for t in selected) / len(selected) if selected else 0

            if avg >= threshold_crore:
                return {
                    "verdict":    "pass",
                    "confidence": 0.91,
                    "evidence":   evidence,
                    "reasoning":  (
                        f"3-year average turnover ₹{avg:.2f} Cr meets the required "
                        f"average of ₹{threshold_crore:.2f} Cr."
                    ),
                    "layer_used": "numeric",
                }
            else:
                return {
                    "verdict":    "fail",
                    "confidence": 0.88,
                    "evidence":   evidence,
                    "reasoning":  (
                        f"3-year average turnover ₹{avg:.2f} Cr is below the required "
                        f"average of ₹{threshold_crore:.2f} Cr."
                    ),
                    "layer_used": "numeric",
                }

        else:
            # ── Per-year path ─────────────────────────────────────────────────
            qualifying_years = [
                t for t in turnovers
                if t["value_crore"] is not None and t["value_crore"] >= threshold_crore
            ]

            if years_required and isinstance(years_required, (int, float)):
                if len(qualifying_years) >= int(years_required):
                    return {
                        "verdict":    "pass",
                        "confidence": 0.90,
                        "evidence":   evidence,
                        "reasoning":  (
                            f"Found {len(qualifying_years)} financial year(s) meeting "
                            f"the ₹{threshold_crore:.2f} Cr threshold. "
                            f"Required: {years_required} year(s)."
                        ),
                        "layer_used": "numeric",
                    }
                else:
                    return {
                        "verdict":    "fail",
                        "confidence": 0.88,
                        "evidence":   evidence,
                        "reasoning":  (
                            f"Only {len(qualifying_years)} year(s) meet the "
                            f"₹{threshold_crore:.2f} Cr threshold. "
                            f"Required: {years_required} year(s)."
                        ),
                        "layer_used": "numeric",
                    }
            else:
                # No specific years required — check if any meet threshold
                if qualifying_years:
                    return {
                        "verdict":    "pass",
                        "confidence": 0.85,
                        "evidence":   evidence,
                        "reasoning":  (
                            f"Turnover of ₹{qualifying_years[0]['value_crore']:.2f} Cr "
                            f"meets the required ₹{threshold_crore:.2f} Cr threshold."
                        ),
                        "layer_used": "numeric",
                    }
                else:
                    highest = max(turnovers, key=lambda t: t["value_crore"] or 0)
                    return {
                        "verdict":    "fail",
                        "confidence": 0.87,
                        "evidence":   evidence,
                        "reasoning":  (
                            f"Highest turnover found: ₹{highest['value_crore']:.2f} Cr. "
                            f"Required minimum: ₹{threshold_crore:.2f} Cr."
                        ),
                        "layer_used": "numeric",
                    }

    # No threshold to compare — fall back to semantic
    return _match_semantic(criterion, bidder_text)


def _parse_threshold_to_crore(threshold_value, criterion_text: str) -> Optional[float]:
    """
    Convert a threshold value string to a float in crores.

    Handles:
      - "2 crore"           → 2.0
      - "175999.50"         → 0.0176  (raw rupees)
      - "30% of 5,86,665"   → computed percentage in crore
      - "30% of estimated cost" with cost in criterion_text
    """
    # ── Percentage-of-cost pattern ────────────────────────────────────────────
    # e.g. criterion: "30% of estimated cost put to tender (Rs. 5,86,665)"
    pct_match = re.search(
        r"(\d+(?:\.\d+)?)\s*%\s*of\s*(?:estimated\s+cost|nit\s+cost|tender\s+cost|the\s+cost)?",
        criterion_text,
        re.IGNORECASE,
    )
    cost_match = re.search(
        r"(?:rs\.?|₹|inr)\s*([\d,]+(?:\.\d+)?)",
        criterion_text,
        re.IGNORECASE,
    )
    if pct_match and cost_match:
        pct  = float(pct_match.group(1)) / 100
        cost = float(cost_match.group(1).replace(",", ""))
        # cost is in rupees; convert to crore
        return round(pct * cost / 1_00_00_000, 6)

    if threshold_value is None:
        # Try to extract from criterion text directly
        match = re.search(
            r"([\d,\.]+)\s*(crore|crores|cr|lakh|lakhs)",
            criterion_text, re.IGNORECASE
        )
        if match:
            threshold_value = f"{match.group(1)} {match.group(2)}"
        else:
            return None

    threshold_str = str(threshold_value).lower().replace(",", "")
    number_match  = re.search(r"[\d\.]+", threshold_str)

    if not number_match:
        return None

    value = float(number_match.group())

    if "lakh" in threshold_str or "lac" in threshold_str:
        return value / 100  # convert lakh to crore
    elif "crore" in threshold_str or re.search(r"\bcr\b", threshold_str):
        return value
    elif "thousand" in threshold_str:
        return value / 100_000
    else:
        return value  # assume crore if no unit


# ── Layer 1b: Technical criterion matching ────────────────────────────────────

def _match_technical(criterion: dict, bidder_facts: dict,
                     bidder_text: str) -> dict:
    """Match technical criteria (experience, certifications, years)."""
    criterion_text = criterion.get("criterion_text", "").lower()
    years_required = criterion.get("years_required")
    
    # Check for ISO/BIS certification requirement
    if "iso" in criterion_text or "bis" in criterion_text:
        iso_certs = bidder_facts.get("iso_certs", [])
        if iso_certs:
            # Check if the specific ISO standard matches
            iso_match = _check_iso_match(criterion_text, iso_certs)
            if iso_match:
                return {
                    "verdict":    "pass",
                    "confidence": 0.92,
                    "evidence":   f"Found: {', '.join(iso_certs)}",
                    "reasoning":  f"ISO certificate found in submitted documents: {iso_match}",
                    "layer_used": "numeric",
                }
            else:
                return {
                    "verdict":    "review",
                    "confidence": 0.65,
                    "evidence":   f"Found certificates: {', '.join(iso_certs)}",
                    "reasoning":  "ISO certificates found but may not match the specific "
                                  "standard required. Please verify.",
                    "layer_used": "numeric",
                }
        else:
            return {
                "verdict":    "review",
                "confidence": 0.55,
                "evidence":   "No ISO/BIS certificates found in documents",
                "reasoning":  "ISO certification mentioned in criterion but no certificate "
                              "found in submitted documents. May be in an image format "
                              "that was not read correctly.",
                "layer_used": "numeric",
            }
    
    # Check for years of experience requirement
    if years_required or "year" in criterion_text:
        required_years  = years_required or _extract_years_from_text(criterion_text)
        bidder_exp_years = bidder_facts.get("years_experience", [])
        
        if bidder_exp_years and required_years:
            max_exp = max(bidder_exp_years)
            if max_exp >= required_years:
                return {
                    "verdict":    "pass",
                    "confidence": 0.82,
                    "evidence":   f"Experience stated: {max_exp} years",
                    "reasoning":  f"{max_exp} years of experience meets "
                                  f"the required {required_years} years.",
                    "layer_used": "numeric",
                }
            else:
                return {
                    "verdict":    "fail",
                    "confidence": 0.80,
                    "evidence":   f"Experience stated: {max_exp} years",
                    "reasoning":  f"Only {max_exp} years of experience found. "
                                  f"Required: {required_years} years.",
                    "layer_used": "numeric",
                }
    
    # Fall back to semantic matching
    return _match_semantic(criterion, bidder_text)


def _check_iso_match(criterion_text: str, certs: list) -> Optional[str]:
    """Check if any found certificate matches what the criterion requires."""
    # Extract ISO standard number from criterion
    iso_match = re.search(r"iso\s*(\d{4})", criterion_text, re.IGNORECASE)
    required_standard = iso_match.group(1) if iso_match else None
    
    for cert in certs:
        if required_standard and required_standard in cert:
            return cert
        if "iso" in cert.lower() and required_standard is None:
            return cert
    return None


def _extract_years_from_text(text: str) -> Optional[int]:
    """Extract a number of years from text like 'minimum 3 years'."""
    match = re.search(r"(\d+)\s*(?:year|yr)", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


# ── Layer 1c: Compliance criterion matching ───────────────────────────────────

def _match_compliance(criterion: dict, bidder_facts: dict,
                      bidder_text: str) -> dict:
    """Match compliance criteria (GST, PAN, registrations, declarations)."""
    criterion_text = criterion.get("criterion_text", "").lower()
    
    # GST registration
    if "gst" in criterion_text or "gstin" in criterion_text:
        gst_numbers = bidder_facts.get("gst_numbers", [])
        if gst_numbers:
            return {
                "verdict":    "pass",
                "confidence": 0.95,
                "evidence":   f"GSTIN found: {gst_numbers[0]}",
                "reasoning":  "Valid GSTIN found in submitted documents.",
                "layer_used": "numeric",
            }
        else:
            return {
                "verdict":    "review",
                "confidence": 0.60,
                "evidence":   "No GSTIN number found in documents",
                "reasoning":  "GST registration required but no GSTIN number detected. "
                              "May be present but in a format not readable by OCR.",
                "layer_used": "numeric",
            }
    
    # PAN registration
    if "pan" in criterion_text:
        pan_numbers = bidder_facts.get("pan_numbers", [])
        if pan_numbers:
            return {
                "verdict":    "pass",
                "confidence": 0.95,
                "evidence":   f"PAN found: {pan_numbers[0]}",
                "reasoning":  "Valid PAN number found in submitted documents.",
                "layer_used": "numeric",
            }
        else:
            return {
                "verdict":    "review",
                "confidence": 0.60,
                "evidence":   "No PAN number found in documents",
                "reasoning":  "PAN required but not detected in submitted documents.",
                "layer_used": "numeric",
            }
    
    # For other compliance criteria, use semantic matching
    return _match_semantic(criterion, bidder_text)


# ── Layer 1d: Documentary criterion matching ──────────────────────────────────

def _match_documentary(criterion: dict, bidder_facts: dict,
                       bidder_text: str) -> dict:
    """
    Match documentary criteria (check if required documents were submitted).
    Uses keyword search + semantic matching.
    """
    criterion_text = criterion.get("criterion_text", "").lower()
    keywords       = criterion.get("keywords", [])
    
    # Check if key document terms appear in bidder text
    doc_keywords = {
        "balance sheet":        ["balance sheet", "financial statement", "audited accounts"],
        "experience certificate": ["experience certificate", "work order", "completion certificate",
                                   "performance certificate"],
        "affidavit":            ["affidavit", "declaration", "self declaration"],
        "power of attorney":    ["power of attorney", "authorisation letter"],
    }
    
    for doc_type, search_terms in doc_keywords.items():
        if any(term in criterion_text for term in [doc_type] + search_terms[:1]):
            found = any(term in bidder_text.lower() for term in search_terms)
            if found:
                matching_term = next(t for t in search_terms if t in bidder_text.lower())
                return {
                    "verdict":    "pass",
                    "confidence": 0.78,
                    "evidence":   f"Found reference to '{matching_term}' in submitted documents",
                    "reasoning":  f"Required document ({doc_type}) appears to be present "
                                  f"in the submission.",
                    "layer_used": "semantic",
                }
    
    # Fall through to semantic matching
    return _match_semantic(criterion, bidder_text)


# ── Layer 2: Semantic matching ─────────────────────────────────────────────────

def _match_semantic(criterion: dict, bidder_text: str) -> dict:
    """
    Use sentence-transformers to compare criterion text with bidder document text.
    
    Strategy:
      1. Split bidder text into paragraphs
      2. Encode all paragraphs as embeddings
      3. Find the paragraph most similar to the criterion
      4. Use the similarity score to decide verdict
    """
    model = get_embedding_model()
    
    criterion_text = criterion.get("criterion_text", "")
    if not criterion_text or not bidder_text:
        return _make_review_result("Insufficient text for matching", "semantic")
    
    # Split bidder text into paragraphs for searching
    paragraphs = [p.strip() for p in bidder_text.split("\n\n") if len(p.strip()) > 30]
    
    if not paragraphs:
        return _make_review_result("No readable paragraphs in bidder documents", "semantic")
    
    # Limit to first 100 paragraphs to avoid memory issues
    paragraphs = paragraphs[:100]
    
    # Encode criterion and all paragraphs
    criterion_embedding  = model.encode(criterion_text, convert_to_tensor=True)
    paragraph_embeddings = model.encode(paragraphs, convert_to_tensor=True)
    
    # Calculate cosine similarity between criterion and each paragraph
    similarities = util.cos_sim(criterion_embedding, paragraph_embeddings)[0]
    
    # Find the most similar paragraph
    best_idx  = similarities.argmax().item()
    best_sim  = similarities[best_idx].item()
    best_para = paragraphs[best_idx]
    
    # ── Map similarity score to verdict ───────────────────────────────────────
    # Cosine similarity: 1.0 = identical, 0.0 = completely different
    # For short/paraphrased sentences, 0.6+ is a good match
    
    if best_sim >= 0.65:
        return {
            "verdict":    "pass",
            "confidence": min(0.85, best_sim),
            "evidence":   f"Best matching paragraph: \"{best_para[:200]}...\"",
            "reasoning":  f"Document content closely matches criterion (similarity: "
                          f"{best_sim:.0%}). Relevant content found in submission.",
            "layer_used": "semantic",
        }
    
    elif best_sim >= 0.45:
        # Ambiguous — escalate to LLM for better judgement
        return _match_with_llm(criterion, best_para, best_sim)
    
    else:
        return {
            "verdict":    "review",
            "confidence": max(0.40, best_sim),
            "evidence":   f"Best match found had low similarity ({best_sim:.0%})",
            "reasoning":  "No clearly relevant content found in bidder documents for "
                          "this criterion. Manual review recommended.",
            "layer_used": "semantic",
        }


# ── Layer 3: LLM reasoning ────────────────────────────────────────────────────

def _match_with_llm(criterion: dict, best_paragraph: str,
                    semantic_score: float) -> dict:
    """
    Ask Mistral to reason about whether the criterion is met.
    Called when semantic similarity is ambiguous (0.45–0.65).
    """
    prompt = f"""You are a government procurement evaluator.

Tender criterion: {criterion.get('criterion_text', '')}

Best matching text found in the bidder's documents:
"{best_paragraph}"

Question: Does the bidder's text satisfy the criterion?

Respond with ONLY a JSON object in this exact format:
{{"verdict": "pass" or "fail" or "review", "confidence": 0.0-1.0, "reasoning": "one sentence explanation"}}

Rules:
- "pass" if the criterion is clearly met
- "fail" if the criterion is clearly not met  
- "review" if you cannot determine with confidence
- confidence should reflect how certain you are
"""
    
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model":   OLLAMA_MODEL,
                "prompt":  prompt,
                "stream":  False,
                "options": {"temperature": 0.1, "num_predict": 200},
            },
            timeout=60,
        )
        response.raise_for_status()
        raw = response.json().get("response", "")
        
        # Parse JSON from response
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            return {
                "verdict":    parsed.get("verdict", "review"),
                "confidence": float(parsed.get("confidence", 0.6)),
                "evidence":   f"Semantic match ({semantic_score:.0%}): \"{best_paragraph[:200]}\"",
                "reasoning":  parsed.get("reasoning", "LLM assessment"),
                "layer_used": "llm",
            }
    
    except Exception as e:
        print(f"[matcher] LLM call failed: {e}")
    
    # LLM failed — return review
    return _make_review_result(
        f"Ambiguous match (similarity: {semantic_score:.0%}). LLM assessment unavailable.",
        "llm"
    )


# ── Batch matching ─────────────────────────────────────────────────────────────

def match_all_criteria(criteria: list, bidder_text: str,
                       bidder_name: str = "Bidder") -> list:
    """
    Match all criteria against one bidder's documents.
    
    Args:
        criteria:    List of criterion dicts from criteria_llm.py
        bidder_text: Full concatenated text of the bidder's documents
        bidder_name: Display name for logging
    
    Returns:
        List of match result dicts
    """
    print(f"\n[matcher] Evaluating {len(criteria)} criteria for: {bidder_name}")
    
    # Extract all facts from bidder text upfront (do this once)
    bidder_facts = extract_bidder_facts(bidder_text)
    
    results = []
    for i, criterion in enumerate(criteria):
        print(f"[matcher] Criterion {i+1}/{len(criteria)}: {criterion.get('id')} "
              f"({criterion.get('category')})")
        
        result = match_criterion(criterion, bidder_facts, bidder_text)
        results.append(result)
    
    # Summary
    verdicts = [r["verdict"] for r in results]
    print(f"[matcher] Done. Pass: {verdicts.count('pass')} | "
          f"Fail: {verdicts.count('fail')} | "
          f"Review: {verdicts.count('review')}")
    
    return results


# ── Helper ─────────────────────────────────────────────────────────────────────

def _make_review_result(reason: str, layer: str) -> dict:
    """Create a standard 'needs review' result."""
    return {
        "verdict":    "review",
        "confidence": 0.50,
        "evidence":   reason,
        "reasoning":  reason,
        "layer_used": layer,
    }


# ── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Sample criterion and bidder text for testing
    sample_criterion = {
        "id":               "C001",
        "criterion_text":   "Bidder shall have annual turnover of not less than "
                            "Rupees Two Crores for last three financial years",
        "category":         "Financial",
        "mandatory":        True,
        "threshold_value":  "2 crore",
        "threshold_unit":   "INR",
        "years_required":   3,
        "section_reference": "Section 4.2",
        "keywords":         ["turnover", "revenue"],
    }
    
    sample_bidder_text = """
    FINANCIAL INFORMATION
    Annual Turnover as certified by CA Firm M/s Mehta & Associates:
    
    FY 2021-22: Rs. 2.8 Crore (Revenue from Operations)
    FY 2022-23: ₹ 3.4 Crore
    FY 2023-24: INR 3.1 Crores
    
    Net Worth: Positive (₹1.2 Crore as on 31.03.2024)
    
    GSTIN: 27AABCS1234M1Z5
    PAN: AABCS1234M
    ISO 9001:2015 certified by Bureau Veritas
    """
    
    print("Testing matcher...\n")
    from app.pipeline.ner import extract_bidder_facts
    facts = extract_bidder_facts(sample_bidder_text)
    result = match_criterion(sample_criterion, facts, sample_bidder_text)
    
    print(f"Verdict:    {result['verdict'].upper()}")
    print(f"Confidence: {result['confidence']:.0%}")
    print(f"Layer:      {result['layer_used']}")
    print(f"Evidence:   {result['evidence']}")
    print(f"Reasoning:  {result['reasoning']}")