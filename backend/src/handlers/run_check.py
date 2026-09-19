"""Asynchronous worker Lambda: fn_run_check.

Triggered asynchronously by POST /packets/{packetId}/check.
Workflow:
1. Loads full packet from DynamoDB using AP2 query (pk='PACKET#<id>').
2. Filters active, non-superseded, extracted documents.
3. Builds Application Snapshot using pure-Python snapshot builder (build_snapshot).
4. Evaluates all 11 MMNBA scheme rules using RuleEngine.
5. Identifies candidate findings flagged with needsAdjudication=True.
6. If candidates exist:
   - Builds Nodal Officer adjudication prompt (adjudicate.py).
   - Invokes Amazon Bedrock Converse API with FindingAdjudication JSON Schema.
   - Runs raw output through all 6 Deterministic Guardrails (apply_all_guardrails).
7. If Bedrock fails, throttles, or unverified:
   - Template Fallback Engine automatically populates YAML defaultReason/defaultFix templates.
   - aiStatus = FALLBACK_TEMPLATE.
8. Computes final readiness score using pure-Python deterministic scoring (compute_readiness_score).
   - Formula: score = max(0, 100 - 25*RED - 10*AMBER).
   - Rating band: READY (>=85), RISKY (60-84), NOT_READY (<60).
9. Assembles typed Verdict Pydantic model.
10. Writes VERDICT#<isoTimestamp> item and updates packet META status to CHECKED (AP5).
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

from ..core.models import (
    Verdict,
    AIStatus,
    PacketStatus,
    DocumentStatus,
    is_usable_extraction,
)
from ..core.snapshot import build_snapshot
from ..core.rules.engine import RuleEngine
from ..core.scoring import compute_readiness_score
from ..ai.adjudicate import build_adjudication_prompt
from ..ai.schemas import get_adjudication_output_config
from ..ai.validation import apply_all_guardrails
from ..aws.bedrock_client import invoke_bedrock_structured, DEFAULT_MODEL_ID
from ..aws.ddb import (
    get_full_packet,
    save_verdict,
    update_packet_status,
)

logger = logging.getLogger(__name__)


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Handle async check run."""
    packet_id = event.get("packetId")
    check_run_id = event.get("checkRunId", "run-default")

    if not packet_id:
        logger.error("Missing packetId in run_check event payload: %s", event)
        return {"status": "FAILED", "error": "Missing packetId"}

    try:
        logger.info("Executing defect check for packet=%s, checkRunId=%s", packet_id, check_run_id)

        # 1. Fetch full packet from DynamoDB
        packet = get_full_packet(packet_id)
        if not packet:
            logger.error("Packet '%s' not found.", packet_id)
            return {"status": "FAILED", "error": f"Packet '{packet_id}' not found."}

        # 2. Filter active, non-superseded documents
        active_docs = []
        for doc in packet.documents:
            if doc.supersededBy is None:
                active_docs.append(doc)

        # Minimum extracted documents guard: require at least 3 usable extracted documents
        active_extracted_docs = [
            doc for doc in active_docs
            if doc.status == DocumentStatus.EXTRACTED
            and doc.extraction is not None
            and is_usable_extraction(doc.extraction)
        ]
        if len(active_extracted_docs) < 3:
            err_msg = (
                f"Cannot run check: at least 3 usable extracted documents are required "
                f"(found {len(active_extracted_docs)})."
            )
            logger.warning("Packet %s check rejected: %s", packet_id, err_msg)
            return {
                "status": "FAILED",
                "packetId": packet_id,
                "error": err_msg,
            }

        # 3. Build Application Snapshot
        snapshot = build_snapshot(active_docs)

        # 4. Run deterministic scheme rules
        engine = RuleEngine()
        raw_findings = engine.evaluate(snapshot, active_docs)
        logger.info("RuleEngine emitted %d raw findings.", len(raw_findings))

        # 5. Extract all known raw and normalized values for evidence grounding guardrail
        known_values: List[str] = []
        for doc in active_docs:
            if doc.extraction and doc.extraction.fields:
                for f in doc.extraction.fields:
                    if f.rawValue:
                        known_values.append(str(f.rawValue))
                    if f.normalizedValue:
                        known_values.append(str(f.normalizedValue))

        # 6. Check if any finding needs AI adjudication
        adjudication_candidates = [f for f in raw_findings if f.needsAdjudication]
        final_findings = raw_findings
        ai_status = AIStatus.OK

        if len(adjudication_candidates) > 0:
            logger.info("Adjudicating %d ambiguous identity findings with Bedrock...", len(adjudication_candidates))
            ai_response_text = None
            try:
                sys_prompt, user_prompt = build_adjudication_prompt(snapshot, adjudication_candidates)
                adj_config = get_adjudication_output_config()
                ai_response_text = invoke_bedrock_structured(
                    system_prompt=sys_prompt,
                    user_prompt=user_prompt,
                    output_config=adj_config,
                    max_tokens=3000,
                )
            except Exception as bed_err:
                logger.warning("Bedrock adjudication failed: %s. Engaging template fallback.", str(bed_err))

            # If Bedrock succeeded: apply all 6 deterministic guardrails
            if ai_response_text:
                final_findings, ai_status = apply_all_guardrails(
                    raw_ai_text=ai_response_text,
                    findings=raw_findings,
                    rules_by_id=engine.rules_by_id,
                    known_values=known_values,
                )
            else:
                # Bedrock unverified/failed: apply template fallback
                final_findings, ai_status = apply_all_guardrails(
                    raw_ai_text="",  # triggers fallback
                    findings=raw_findings,
                    rules_by_id=engine.rules_by_id,
                    known_values=known_values,
                )
                ai_status = AIStatus.FALLBACK_TEMPLATE

        # 7. Pure-Python deterministic scoring (LLM NEVER computes score!)
        score, band, arithmetic = compute_readiness_score(final_findings)
        logger.info("Computed readiness score: %d (%s) -> '%s'", score, band.value, arithmetic)

        # 8. Construct Verdict object
        now_iso = datetime.now(timezone.utc).isoformat()
        verdict = Verdict(
            checkRunId=check_run_id,
            snapshot=snapshot,
            findings=final_findings,
            score=score,
            band=band,
            scoreArithmetic=arithmetic,
            ruleSetVersion="NIJUT_BABU_2026@1",
            modelId=DEFAULT_MODEL_ID,
            aiStatus=ai_status,
            createdAt=now_iso,
        )

        # 9. Save verdict & update packet status to CHECKED (AP5)
        save_verdict(packet_id, verdict)
        logger.info("Verdict saved successfully for packet %s. Status -> CHECKED.", packet_id)

        return {
            "status": "SUCCESS",
            "packetId": packet_id,
            "checkRunId": check_run_id,
            "score": score,
            "band": band.value,
        }

    except Exception as e:
        logger.exception("Fatal error in run_check worker: %s", str(e))
        update_packet_status(packet_id, PacketStatus.READY_TO_CHECK)
        return {"status": "FAILED", "error": str(e)}
