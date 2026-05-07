"""
ner.py — Named Entity Recognition for Indian financial documents
----------------------------------------------------------------
Extracts structured facts from bidder documents using spaCy + custom rules.

Why custom rules and not a pre-trained model?
  Generic English NER models (even good ones) are trained on Western text.
  They have never seen:
    - "₹ 3.4 crore" or "Rs. 340 lakhs"
    - "FY 2021-22" (Indian financial year format)
    - "GSTIN: 29AABCT1332L1ZN"
    - "CIN: U17200MH2015PTC123456"
  
  spaCy's EntityRuler lets us define EXACT PATTERNS for these entities
  using regex-like rules. No training data needed. Works immediately.
  For the hackathon prototype, this is the right approach.

Entities this module extracts:
  - MONEY_INR    : ₹ amounts (crore, lakh, thousand formats)
  - FINANCIAL_YEAR: Indian FY format (2021-22, FY 2022-23)
  - GST_NUMBER   : GSTIN in standard format
  - PAN_NUMBER   : PAN card number
  - CIN_NUMBER   : Company Identification Number
  - ISO_CERT     : ISO certificate references
  - DATE         : Dates (various formats)
  - ORG_GOV      : Government organisation names
  - YEARS_EXP    : Years of experience statements

Usage:
  from app.pipeline.ner import extract_entities
  entities = extract_entities("The company had turnover of ₹3.4 crore in FY 2023-24")
  # returns list of {text, label, value, confidence}
"""

import re
import spacy
from spacy.language import Language
from spacy.pipeline import EntityRuler


# ── Load spaCy model ───────────────────────────────────────────────────────────
# "en_core_web_sm" is a small, fast English model. It handles tokenisation
# and basic NLP. We ADD our custom rules on top of it.
#
# If you haven't downloaded it yet:
#   python -m spacy download en_core_web_sm

_nlp = None  # Lazy-loaded — only initialised on first use


def get_nlp():
    """Get the spaCy pipeline (loads once, reuses after that)."""
    global _nlp
    if _nlp is None:
        print("[ner] Loading spaCy model...")
        _nlp = _build_nlp_pipeline()
        print("[ner] spaCy model loaded")
    return _nlp


def _build_nlp_pipeline() -> Language:
    """
    Build a spaCy NLP pipeline with our custom entity patterns.
    
    The EntityRuler matches text patterns BEFORE the statistical NER model,
    so our Indian-specific entities always take priority.
    """
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        raise OSError(
            "spaCy model 'en_core_web_sm' not found.\n"
            "Install it with: python -m spacy download en_core_web_sm"
        )

    # Add EntityRuler BEFORE the built-in NER component
    # "overwrite_ents=True" means our rules override spaCy's default entities
    ruler = nlp.add_pipe(
        "entity_ruler",
        before="ner",
        config={"overwrite_ents": True}
    )

    # Add all our custom patterns
    ruler.add_patterns(_get_patterns())

    return nlp


def _get_patterns() -> list:
    """
    Define pattern rules for Indian financial and legal entities.
    
    Each pattern has:
      - label: the entity type (e.g. "MONEY_INR")
      - pattern: list of token matchers OR a regex string
    
    spaCy pattern matching reference:
      https://spacy.io/usage/rule-based-matching
    """
    patterns = []

    # ── MONEY_INR: Indian Rupee amounts ───────────────────────────────────────
    # Covers: ₹3.4 crore, Rs 340 lakhs, INR 2,00,000, rupees two crores
    # Token pattern: [optional ₹/Rs/INR] [number] [optional crore/lakh/thousand]
    
    money_patterns = [
        # Pattern: ₹ 3.4 crore / ₹3.4 crore / ₹ 3,40,000
        {
            "label": "MONEY_INR",
            "pattern": [
                {"TEXT": {"REGEX": r"[₹Rs\.INR]+"}},
                {"TEXT": {"REGEX": r"[\d,\.]+"}},
                {"LOWER": {"IN": ["crore", "crores", "cr", "lakh", "lakhs", "lac",
                                   "lacs", "thousand", "thousands", "million"]},
                 "OP": "?"},
            ]
        },
        # Pattern: 3.4 crore / 340 lakhs (without currency symbol)
        {
            "label": "MONEY_INR",
            "pattern": [
                {"TEXT": {"REGEX": r"[\d,\.]+"}},
                {"LOWER": {"IN": ["crore", "crores", "cr.", "lakh", "lakhs",
                                   "lac", "lacs"]}},
            ]
        },
        # Pattern: rupees two crores (word form)
        {
            "label": "MONEY_INR",
            "pattern": [
                {"LOWER": {"IN": ["rupees", "rs.", "inr"]}},
                {"POS": {"IN": ["NUM", "ADJ", "NOUN"]}, "OP": "+"},
                {"LOWER": {"IN": ["crore", "crores", "lakh", "lakhs"]}, "OP": "?"},
            ]
        },
    ]
    patterns.extend(money_patterns)

    # ── FINANCIAL_YEAR: Indian financial year format ───────────────────────────
    # Covers: FY 2021-22, 2021-2022, FY2023-24, financial year 2022-23
    fy_patterns = [
        {
            "label": "FINANCIAL_YEAR",
            "pattern": [
                {"LOWER": {"IN": ["fy", "f.y.", "fy."]}},
                {"TEXT": {"REGEX": r"20\d{2}[-–]\d{2,4}"}},
            ]
        },
        {
            "label": "FINANCIAL_YEAR",
            "pattern": [
                {"LOWER": {"IN": ["financial"]}},
                {"LOWER": {"IN": ["year", "yr"]}},
                {"TEXT": {"REGEX": r"20\d{2}[-–]\d{2,4}"}},
            ]
        },
        # Standalone: 2021-22 (common in Indian documents)
        {
            "label": "FINANCIAL_YEAR",
            "pattern": [
                {"TEXT": {"REGEX": r"20\d{2}[-–]2\d"}}
            ]
        },
    ]
    patterns.extend(fy_patterns)

    # ── GST_NUMBER: GSTIN format (15-character alphanumeric) ──────────────────
    # Format: 2-digit state code + 10-char PAN + 1 entity number + Z + check digit
    # Example: 29AABCT1332L1ZN
    patterns.append({
        "label": "GST_NUMBER",
        "pattern": [
            {"TEXT": {"REGEX": r"\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z0-9]"}}
        ]
    })
    # With label prefix: GSTIN: 29AABCT1332L1ZN
    patterns.append({
        "label": "GST_NUMBER",
        "pattern": [
            {"LOWER": {"IN": ["gstin", "gst", "gstin:"]}},
            {"TEXT": {"REGEX": r"\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z0-9]"}},
        ]
    })

    # ── PAN_NUMBER: Permanent Account Number ──────────────────────────────────
    # Format: 5 letters + 4 digits + 1 letter
    # Example: AABCT1332L
    patterns.append({
        "label": "PAN_NUMBER",
        "pattern": [
            {"TEXT": {"REGEX": r"[A-Z]{5}\d{4}[A-Z]"}}
        ]
    })
    patterns.append({
        "label": "PAN_NUMBER",
        "pattern": [
            {"LOWER": {"IN": ["pan", "pan:"]}},
            {"TEXT": {"REGEX": r"[A-Z]{5}\d{4}[A-Z]"}},
        ]
    })

    # ── CIN_NUMBER: Company Identification Number ──────────────────────────────
    # Format: L/U + 5 digits + 2 letters + 4 digits + 3 letters + 6 digits
    # Example: U17200MH2015PTC123456
    patterns.append({
        "label": "CIN_NUMBER",
        "pattern": [
            {"TEXT": {"REGEX": r"[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}"}}
        ]
    })

    # ── ISO_CERT: ISO certificate references ──────────────────────────────────
    # Covers: ISO 9001:2015, ISO 9001, BIS certificate
    patterns.append({
        "label": "ISO_CERT",
        "pattern": [
            {"LOWER": "iso"},
            {"TEXT": {"REGEX": r"\d{4}"}},
            {"TEXT": ":"},
            {"TEXT": {"REGEX": r"20\d{2}"}},
        ]
    })
    patterns.append({
        "label": "ISO_CERT",
        "pattern": [
            {"LOWER": "iso"},
            {"TEXT": {"REGEX": r"\d{4}"}},
        ]
    })
    patterns.append({
        "label": "ISO_CERT",
        "pattern": [
            {"LOWER": {"IN": ["bis", "isi"]}},
            {"LOWER": {"IN": ["certificate", "certified", "mark", "licence"]}, "OP": "?"},
        ]
    })

    # ── YEARS_EXP: Years of experience ────────────────────────────────────────
    # Covers: "3 years of experience", "five years", "minimum 3 years"
    patterns.append({
        "label": "YEARS_EXP",
        "pattern": [
            {"TEXT": {"REGEX": r"\d+"}},
            {"LOWER": {"IN": ["year", "years", "yr", "yrs"]}},
            {"LOWER": {"IN": ["of", "in"]}, "OP": "?"},
            {"LOWER": {"IN": ["experience", "exp", "service", "operation",
                               "supply", "supplies"]}, "OP": "?"},
        ]
    })

    # ── ORG_GOV: Government organisation references ────────────────────────────
    gov_orgs = [
        "crpf", "cisf", "bsf", "itbp", "ssb", "nsf", "capf",
        "ministry", "department", "directorate", "government of india",
        "central government", "state government", "defence",
        "railways", "irctc", "nic", "ntpc", "ongc", "hal",
        "drdo", "isro", "bsnl", "sail",
    ]
    patterns.append({
        "label": "ORG_GOV",
        "pattern": [{"LOWER": {"IN": gov_orgs}}]
    })

    # ── DATE patterns (Indian format) ─────────────────────────────────────────
    # dd-mm-yyyy, dd/mm/yyyy, dd.mm.yyyy
    patterns.append({
        "label": "DATE_IND",
        "pattern": [
            {"TEXT": {"REGEX": r"\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4}"}}
        ]
    })

    return patterns


# ── Main extraction function ───────────────────────────────────────────────────

def extract_entities(text: str) -> list:
    """
    Extract all named entities from text.
    
    Args:
        text: Plain text from a bidder document
    
    Returns:
        List of entity dicts:
          {
            "text":       "₹3.4 crore",
            "label":      "MONEY_INR",
            "start":      45,        # character position in text
            "end":        55,
            "normalized": 3.4,       # cleaned/normalised value (where applicable)
            "unit":       "crore",
          }
    """
    nlp = get_nlp()
    
    if not text or not text.strip():
        return []

    # spaCy processes the text in one call
    doc = nlp(text[:100_000])  # cap at 100k chars to avoid memory issues

    entities = []
    for ent in doc.ents:
        entity = {
            "text":       ent.text,
            "label":      ent.label_,
            "start":      ent.start_char,
            "end":        ent.end_char,
            "normalized": None,
            "unit":       None,
        }

        # ── Normalise specific entity types ──────────────────────────────────
        if ent.label_ == "MONEY_INR":
            value, unit = _normalise_money(ent.text)
            entity["normalized"] = value
            entity["unit"]       = unit

        elif ent.label_ == "FINANCIAL_YEAR":
            entity["normalized"] = _normalise_fy(ent.text)

        elif ent.label_ == "YEARS_EXP":
            entity["normalized"] = _extract_number(ent.text)

        entities.append(entity)

    return entities


def extract_entities_by_type(text: str, label: str) -> list:
    """
    Convenience function: extract only entities of a specific type.
    
    Example:
        money = extract_entities_by_type(text, "MONEY_INR")
    """
    all_entities = extract_entities(text)
    return [e for e in all_entities if e["label"] == label]


# ── Normalisation helpers ──────────────────────────────────────────────────────

def _normalise_money(text: str):
    """
    Convert an Indian money string to a float value in Crores.
    
    Examples:
      "₹3.4 crore"  → (3.4,   "crore")
      "340 lakhs"   → (3.4,   "crore")   ← converted to crore
      "Rs. 50,000"  → (0.0005, "crore")
      "1,75,999.50" → (0.0176, "crore")
    
    Returns:
        (value_in_crore: float, original_unit: str)
        Returns (None, None) if the text looks like a header or non-value.
    """
    text_clean = text.lower().strip()

    # ── Reject header/label-only tokens ──────────────────────────────────────
    # e.g. "TURNOVER (RS. CR)" or "RS. CR}" — no digit present
    if not re.search(r"\d", text_clean):
        return None, None

    # Strip currency symbols and labels
    text_clean = (text_clean
                  .replace("₹", "")
                  .replace("rs.", "")
                  .replace("rs", "")
                  .replace("inr", "")
                  .strip())

    # Remove Indian-style comma separators before parsing number
    # "1,75,999.50" → "175999.50"
    # But keep commas only when they look like thousand-separators
    text_no_comma = re.sub(r"(\d),(\d)", r"\1\2", text_clean)

    # Extract the first numeric value
    number_match = re.search(r"\d+(?:\.\d+)?", text_no_comma)
    if not number_match:
        return None, None

    value = float(number_match.group())

    # Determine unit and convert to crore
    # Use word-boundary aware check so "cr." "cr)" "cr}" all match
    if re.search(r"\bcrore", text_clean) or re.search(r"\bcr\b", text_clean):
        return value, "crore"
    elif re.search(r"\blakh", text_clean) or re.search(r"\blac\b", text_clean):
        return round(value / 100, 4), "crore"   # lakh → crore
    elif "thousand" in text_clean:
        return round(value / 100_000, 6), "crore"
    elif "million" in text_clean:
        return round(value / 10, 4), "crore"    # 1 million = 0.1 crore
    else:
        # Raw rupees — divide by 1 crore
        return round(value / 1_00_00_000, 8), "crore"


def _normalise_fy(text: str) -> str:
    """
    Normalise financial year to standard "YYYY-YY" format.
    
    Examples:
      "FY 2021-22"    → "2021-22"
      "2021-2022"     → "2021-22"
      "fy2023-24"     → "2023-24"
    """
    # Remove "FY", "F.Y.", spaces
    clean = re.sub(r"(?i)f\.?y\.?\s*", "", text).strip()
    
    # If it's in "2021-2022" format, convert to "2021-22"
    match = re.match(r"(20\d{2})[-–](20\d{2})", clean)
    if match:
        start_year = match.group(1)
        end_year   = match.group(2)[-2:]  # take last 2 digits
        return f"{start_year}-{end_year}"
    
    return clean


def _extract_number(text: str) -> float:
    """Extract the first number from a string."""
    match = re.search(r"\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


# ── Structured entity extraction for a full bidder document ───────────────────

def extract_bidder_facts(text: str) -> dict:
    """
    High-level function that extracts ALL relevant facts from a bidder document
    and organises them into a structured dict ready for the matching engine.
    
    Args:
        text: Full text of one bidder's documents (concatenated)
    
    Returns:
        {
          "turnover_values":   [{"fy": "2021-22", "value_crore": 3.4}, ...],
          "gst_numbers":       ["29AABCT1332L1ZN"],
          "pan_numbers":       ["AABCT1332L"],
          "cin_numbers":       ["U17200MH2015PTC123456"],
          "iso_certs":         ["ISO 9001:2015"],
          "years_experience":  [3, 5],
          "gov_orgs_mentioned":["Ministry of Defence"],
          "financial_years":   ["2021-22", "2022-23", "2023-24"],
          "all_entities":      [...],   # full entity list
        }
    """
    entities = extract_entities(text)
    
    facts = {
        "turnover_values":    [],
        "gst_numbers":        [],
        "pan_numbers":        [],
        "cin_numbers":        [],
        "iso_certs":          [],
        "years_experience":   [],
        "gov_orgs_mentioned": [],
        "financial_years":    [],
        "all_entities":       entities,
    }

    # ── Pass 1: Table-aware extraction ────────────────────────────────────────
    # Annual turnover certificates have a table like:
    #   2022 – 23    0.31    1.86
    #   2023 – 24    0.39    2.73
    # This regex captures FY + first numeric column (turnover) directly from
    # the OCR text, bypassing the spaCy entity association which struggles
    # when the table is flattened to a single line.
    #
    # Pattern breakdown:
    #   (20\d{2}\s*[-–]\s*\d{2}) — financial year like "2022 – 23" or "2022-23"
    #   \s+                        — whitespace between columns
    #   ([\d,]+(?:\.\d+)?)         — the turnover figure (first numeric column)
    # We skip rows that are header lines (contain YEAR / TURNOVER / PROFIT).
    table_row_re = re.compile(
        r"(20\d{2}\s*[-–]\s*\d{2})\s+([\d,]+(?:\.\d+)?)",
        re.IGNORECASE,
    )
    seen_fys = set()
    for m in table_row_re.finditer(text):
        raw_fy   = m.group(1)
        raw_val  = m.group(2)

        # Skip if the surrounding context looks like a header or NIT ref
        context_before = text[max(0, m.start()-30):m.start()].upper()
        if any(k in context_before for k in ("YEAR", "TURNOVER", "NIT", "CELL")):
            continue

        fy_norm = _normalise_fy(raw_fy)

        # Validate it's a genuine FY (end year = start year + 1)
        fy_match = re.match(r"(20\d{2})[-–](\d{2})", fy_norm)
        if fy_match:
            if int(fy_match.group(2)) != (int(fy_match.group(1)) + 1) % 100:
                continue
        else:
            continue

        # Parse value — assumed to be in Crore on a turnover statement
        try:
            value_crore = float(raw_val.replace(",", ""))
        except ValueError:
            continue

        # Skip suspiciously large values (likely a mis-parsed number, e.g. PAN/UDIN)
        if value_crore > 10_000:
            continue

        if fy_norm not in seen_fys:
            seen_fys.add(fy_norm)
            facts["turnover_values"].append({
                "fy":          fy_norm,
                "value_crore": value_crore,
                "original":    m.group(0).strip(),
            })
            if fy_norm not in facts["financial_years"]:
                facts["financial_years"].append(fy_norm)

    # ── Pass 2: spaCy entity-based extraction (fills gaps) ───────────────────
    # Run the spaCy entity loop only for entity types OTHER than turnover,
    # and also as a fallback for turnover if the table pass found nothing.
    table_pass_found_turnover = bool(facts["turnover_values"])

    fy_mentions = []
    for ent in entities:
        label = ent["label"]

        if label == "FINANCIAL_YEAR":
            fy_str = ent["normalized"] or ent["text"]
            if fy_str and fy_str not in facts["financial_years"]:
                facts["financial_years"].append(fy_str)
                fy_mentions.append(fy_str)

        elif label == "MONEY_INR" and ent["normalized"] is not None:
            if not table_pass_found_turnover:
                # Fallback: use spaCy entity + nearby FY association
                nearby_fy = _find_nearby_fy(text, ent["start"], ent["end"])
                facts["turnover_values"].append({
                    "fy":          nearby_fy,
                    "value_crore": ent["normalized"],
                    "original":    ent["text"],
                })

        elif label == "GST_NUMBER":
            if ent["text"] not in facts["gst_numbers"]:
                facts["gst_numbers"].append(ent["text"])

        elif label == "PAN_NUMBER":
            if ent["text"] not in facts["pan_numbers"]:
                facts["pan_numbers"].append(ent["text"])

        elif label == "CIN_NUMBER":
            if ent["text"] not in facts["cin_numbers"]:
                facts["cin_numbers"].append(ent["text"])

        elif label == "ISO_CERT":
            if ent["text"] not in facts["iso_certs"]:
                facts["iso_certs"].append(ent["text"])

        elif label == "YEARS_EXP" and ent["normalized"] is not None:
            facts["years_experience"].append(ent["normalized"])

        elif label == "ORG_GOV":
            if ent["text"] not in facts["gov_orgs_mentioned"]:
                facts["gov_orgs_mentioned"].append(ent["text"])

    return facts


def _find_nearby_fy(text: str, start: int, end: int, window: int = 150) -> str:
    """
    Look in a window of text around a money entity for a financial year mention.
    This associates "₹3.4 crore" with "FY 2023-24" if they appear close together.

    Only matches genuine Indian financial years of the form YYYY-YY (e.g. 2022-23)
    where the second part is exactly two digits and represents the next year
    (e.g. 2022-23, 2023-24, 2024-25).  This prevents matching NIT reference
    numbers like "2026-27-CZ-C" or dates like "2026-27" that happen to be nearby.
    """
    context_start = max(0, start - window)
    context_end   = min(len(text), end + window)
    context       = text[context_start:context_end]

    # Strict pattern: optional "FY " prefix, then 20YY-YY where YY = start_year+1
    # We validate that the two-digit suffix is start_year+1 to avoid false matches.
    for m in re.finditer(
        r"(?:FY\s*|financial\s+year\s*)?(20\d{2})[-–](\d{2})\b",
        context,
        re.IGNORECASE,
    ):
        start_yr = int(m.group(1))
        end_yy   = int(m.group(2))
        expected_yy = (start_yr + 1) % 100
        if end_yy == expected_yy:
            return f"{m.group(1)}-{m.group(2)}"

    return None


# ── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    
    sample_text = """
    BIDDER PROFILE — M/s Sunrise Textiles Pvt Ltd
    CIN: U17200MH2015PTC123456
    GSTIN: 27AABCS1234M1Z5
    PAN: AABCS1234M
    
    FINANCIAL DETAILS:
    Annual Turnover (as certified by CA):
    FY 2021-22: ₹ 2.8 Crore
    FY 2022-23: Rs. 3.4 crore
    FY 2023-24: INR 3.1 Crores
    
    The company holds ISO 9001:2015 certification from Bureau Veritas.
    
    Experience: 5 years of experience supplying uniform fabric to 
    Maharashtra State Police and Ministry of Defence units.
    """
    
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            sample_text = f.read()
    
    print("Testing NER extraction...\n")
    facts = extract_bidder_facts(sample_text)
    
    print("── Extracted Facts ──")
    print(f"Turnover values:    {facts['turnover_values']}")
    print(f"Financial years:    {facts['financial_years']}")
    print(f"GST numbers:        {facts['gst_numbers']}")
    print(f"PAN numbers:        {facts['pan_numbers']}")
    print(f"CIN numbers:        {facts['cin_numbers']}")
    print(f"ISO certs:          {facts['iso_certs']}")
    print(f"Years experience:   {facts['years_experience']}")
    print(f"Govt orgs:          {facts['gov_orgs_mentioned']}")
    print(f"\nTotal entities:     {len(facts['all_entities'])}")