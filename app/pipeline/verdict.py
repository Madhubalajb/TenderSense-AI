"""
verdict.py — Verdict Engine
-----------------------------
Takes raw match results from matcher.py and produces final, structured verdicts
for each bidder across all criteria.

This module:
  1. Aggregates criterion-level match results per bidder
  2. Applies the overall bidder verdict logic (eligible/ineligible/review)
  3. Generates plain-language explanations for each verdict
  4. Produces a summary suitable for the dashboard and export

Design principle:
  A bidder is ELIGIBLE only if ALL mandatory criteria are PASS.
  A single mandatory FAIL → bidder is INELIGIBLE.
  Any REVIEW (flagged) criterion → officer must review before locking.
  Optional criteria failures do not change eligibility.

Usage:
  from app.pipeline.verdict import compute_bidder_verdict, compute_all_verdicts
  verdict = compute_bidder_verdict(criteria, match_results, bidder_name)
"""

from typing import Optional


# ── Overall bidder verdict logic ───────────────────────────────────────────────

def compute_bidder_verdict(criteria: list, match_results: list,
                            bidder_name: str = "Bidder") -> dict:
    """
    Compute the overall verdict for one bidder based on all criterion results.
    
    Args:
        criteria:      List of criterion dicts (from criteria_llm.py)
        match_results: List of match result dicts (from matcher.match_all_criteria)
        bidder_name:   Display name for this bidder
    
    Returns:
        {
          "bidder_name":     "Sunrise Textiles Pvt Ltd",
          "overall_verdict": "eligible" | "ineligible" | "review",
          "overall_confidence": 0.87,
          "total_criteria":  12,
          "passed":          10,
          "failed":          1,
          "review_needed":   1,
          "criteria_results": [...],    # enriched per-criterion results
          "fail_reasons":    [...],     # list of reason strings for ineligible
          "review_reasons":  [...],     # list of reason strings for review items
          "summary":         "...",     # plain-language summary for officer
        }
    """
    # Build a lookup: criterion_id → match_result
    results_by_id = {r.get("criterion_id"): r for r in match_results}
    
    # ── Enrich each criterion result ──────────────────────────────────────────
    enriched_results = []
    for criterion in criteria:
        cid    = criterion.get("id")
        result = results_by_id.get(cid)
        
        if result is None:
            # No result for this criterion — mark as review
            result = {
                "criterion_id":  cid,
                "verdict":       "review",
                "confidence":    0.0,
                "evidence":      "Not evaluated",
                "reasoning":     "This criterion was not evaluated — may be a processing error.",
                "layer_used":    "none",
                "needs_review":  True,
            }
        
        # Merge criterion fields into result for display
        enriched = {**result}
        enriched["criterion_text"]   = criterion.get("criterion_text", "")
        enriched["category"]         = criterion.get("category", "")
        enriched["mandatory"]        = criterion.get("mandatory", True)
        enriched["section_reference"] = criterion.get("section_reference", "")
        enriched["threshold_value"]  = criterion.get("threshold_value")
        
        enriched_results.append(enriched)
    
    # ── Count verdicts ─────────────────────────────────────────────────────────
    pass_count   = sum(1 for r in enriched_results if r["verdict"] == "pass")
    fail_count   = sum(1 for r in enriched_results if r["verdict"] == "fail")
    review_count = sum(1 for r in enriched_results if r["verdict"] == "review")
    total        = len(enriched_results)
    
    # ── Mandatory failures and reviews ────────────────────────────────────────
    mandatory_fails   = [r for r in enriched_results
                         if r["verdict"] == "fail" and r.get("mandatory", True)]
    mandatory_reviews = [r for r in enriched_results
                         if r["verdict"] == "review" and r.get("mandatory", True)]
    
    fail_reasons   = [f"{r['criterion_id']}: {r['reasoning']}" for r in mandatory_fails]
    review_reasons = [f"{r['criterion_id']}: {r['reasoning']}" for r in mandatory_reviews]
    
    # ── Overall verdict ────────────────────────────────────────────────────────
    if mandatory_fails:
        overall_verdict = "ineligible"
    elif mandatory_reviews:
        overall_verdict = "review"  # Cannot confirm eligible until reviews are done
    else:
        overall_verdict = "eligible"
    
    # ── Overall confidence ─────────────────────────────────────────────────────
    if enriched_results:
        confidences      = [r.get("confidence", 0.5) for r in enriched_results]
        avg_confidence   = sum(confidences) / len(confidences)
        
        # Penalise confidence if there are review items (uncertainty)
        if review_count > 0:
            avg_confidence *= (1 - (review_count / total) * 0.2)
    else:
        avg_confidence = 0.0
    
    # ── Plain-language summary ─────────────────────────────────────────────────
    summary = _build_summary(
        bidder_name, overall_verdict, pass_count, fail_count,
        review_count, total, fail_reasons, review_reasons
    )
    
    return {
        "bidder_name":        bidder_name,
        "overall_verdict":    overall_verdict,
        "overall_confidence": round(avg_confidence, 3),
        "total_criteria":     total,
        "passed":             pass_count,
        "failed":             fail_count,
        "review_needed":      review_count,
        "criteria_results":   enriched_results,
        "fail_reasons":       fail_reasons,
        "review_reasons":     review_reasons,
        "summary":            summary,
    }


def _build_summary(bidder_name: str, verdict: str, passed: int,
                   failed: int, review: int, total: int,
                   fail_reasons: list, review_reasons: list) -> str:
    """Build a plain-language summary for the officer dashboard."""
    
    if verdict == "eligible":
        return (
            f"{bidder_name} meets all {total} eligibility criteria. "
            f"All mandatory requirements are satisfied. "
            f"This bidder is eligible for technical/commercial evaluation."
        )
    
    elif verdict == "ineligible":
        reason_text = "; ".join(fail_reasons[:2])  # show first 2 reasons
        if len(fail_reasons) > 2:
            reason_text += f" (and {len(fail_reasons) - 2} more)"
        return (
            f"{bidder_name} does not meet {failed} mandatory criterion/criteria. "
            f"Key failure(s): {reason_text}. "
            f"This bidder is ineligible and should be excluded from further evaluation."
        )
    
    else:  # review
        return (
            f"{bidder_name} has {review} criterion/criteria flagged for review. "
            f"{passed} criteria passed and {failed} failed. "
            f"Officer review is required before a final verdict can be recorded."
        )


# ── Batch: all bidders ─────────────────────────────────────────────────────────

def compute_all_verdicts(criteria: list, bidder_evaluations: dict) -> list:
    """
    Compute verdicts for all bidders.
    
    Args:
        criteria: List of all criteria dicts
        bidder_evaluations: {
            "Bidder A": [match_result_1, match_result_2, ...],
            "Bidder B": [match_result_1, match_result_2, ...],
        }
    
    Returns:
        List of verdict dicts sorted by: eligible first, then review, then ineligible.
    """
    all_verdicts = []
    
    for bidder_name, match_results in bidder_evaluations.items():
        verdict = compute_bidder_verdict(criteria, match_results, bidder_name)
        all_verdicts.append(verdict)
    
    # Sort: eligible → review → ineligible
    order = {"eligible": 0, "review": 1, "ineligible": 2}
    all_verdicts.sort(key=lambda v: order.get(v["overall_verdict"], 3))
    
    return all_verdicts


# ── Dashboard summary stats ────────────────────────────────────────────────────

def compute_evaluation_summary(all_verdicts: list) -> dict:
    """
    Compute aggregate statistics across all bidders for the dashboard.
    
    Returns:
        {
          "total_bidders":    8,
          "eligible":         3,
          "ineligible":       3,
          "review":           2,
          "avg_confidence":   0.87,
          "total_criteria":   12,
        }
    """
    if not all_verdicts:
        return {}
    
    eligible   = sum(1 for v in all_verdicts if v["overall_verdict"] == "eligible")
    ineligible = sum(1 for v in all_verdicts if v["overall_verdict"] == "ineligible")
    review     = sum(1 for v in all_verdicts if v["overall_verdict"] == "review")
    
    confidences   = [v["overall_confidence"] for v in all_verdicts]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    
    return {
        "total_bidders":   len(all_verdicts),
        "eligible":        eligible,
        "ineligible":      ineligible,
        "review":          review,
        "avg_confidence":  round(avg_confidence, 3),
        "total_criteria":  all_verdicts[0]["total_criteria"] if all_verdicts else 0,
    }


# ── Officer override ───────────────────────────────────────────────────────────

def apply_officer_override(verdict_dict: dict, criterion_id: str,
                            new_verdict: str, officer_comment: str,
                            officer_name: str) -> dict:
    """
    Apply an officer's manual override to a specific criterion verdict.
    Updates the verdict dict in-place and recomputes the overall verdict.
    
    Args:
        verdict_dict:    The full bidder verdict dict
        criterion_id:    Which criterion to override (e.g. "C003")
        new_verdict:     "pass" or "fail"
        officer_comment: Reason for override (required)
        officer_name:    Name/ID of the officer making the change
    
    Returns:
        Updated verdict dict
    """
    import time
    
    for result in verdict_dict["criteria_results"]:
        if result["criterion_id"] == criterion_id:
            old_verdict = result["verdict"]
            
            # Apply override
            result["verdict"]          = new_verdict
            result["confidence"]       = 1.0  # Officer decision = 100% confident
            result["needs_review"]     = False
            result["officer_override"] = {
                "previous_verdict": old_verdict,
                "new_verdict":      new_verdict,
                "comment":          officer_comment,
                "officer":          officer_name,
                "timestamp":        time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            result["reasoning"] = (
                f"[OFFICER OVERRIDE by {officer_name}] {officer_comment} "
                f"(Previous AI verdict: {old_verdict})"
            )
            break
    
    # Recompute overall verdict based on updated results
    criteria = [
        {
            "id":        r["criterion_id"],
            "mandatory": r.get("mandatory", True),
        }
        for r in verdict_dict["criteria_results"]
    ]
    
    updated = compute_bidder_verdict(
        criteria,
        verdict_dict["criteria_results"],
        verdict_dict["bidder_name"],
    )
    
    # Keep the criteria results (they have overrides in them)
    updated["criteria_results"] = verdict_dict["criteria_results"]
    
    return updated


# ── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Simulate some match results and compute verdict
    sample_criteria = [
        {"id": "C001", "criterion_text": "Turnover ≥ ₹2 Cr",
         "category": "Financial", "mandatory": True},
        {"id": "C002", "criterion_text": "GST registration",
         "category": "Compliance", "mandatory": True},
        {"id": "C003", "criterion_text": "ISO 9001:2015",
         "category": "Technical", "mandatory": True},
    ]
    
    sample_results = [
        {"criterion_id": "C001", "verdict": "pass",   "confidence": 0.92,
         "evidence": "₹3.4 Cr found", "reasoning": "Exceeds threshold",
         "layer_used": "numeric", "needs_review": False},
        {"criterion_id": "C002", "verdict": "pass",   "confidence": 0.95,
         "evidence": "GSTIN found",   "reasoning": "Valid GSTIN",
         "layer_used": "numeric", "needs_review": False},
        {"criterion_id": "C003", "verdict": "review", "confidence": 0.65,
         "evidence": "ISO cert found but year unclear",
         "reasoning": "Certificate found but validity date not legible",
         "layer_used": "semantic", "needs_review": True},
    ]
    
    verdict = compute_bidder_verdict(sample_criteria, sample_results, "Sunrise Textiles")
    
    print(f"Overall verdict:    {verdict['overall_verdict'].upper()}")
    print(f"Overall confidence: {verdict['overall_confidence']:.0%}")
    print(f"Passed:  {verdict['passed']} | Failed: {verdict['failed']} | "
          f"Review: {verdict['review_needed']}")
    print(f"\nSummary:\n{verdict['summary']}")