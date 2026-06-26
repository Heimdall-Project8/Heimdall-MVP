"""
nodes.py — LangGraph investigation + dispatch nodes.

The simulator is now a background thread (simulator.py).
These nodes only handle: investigate anomaly → dispatch alert.

Node flow inside the graph:
  investigate → dispatch → [loop back to investigate if queue non-empty]
"""

import json
import os
from typing import Literal

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

import database
from state import SecurityState

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))

_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not _api_key:
    raise EnvironmentError(
        "❌ GEMINI_API_KEY not found. Put it in your .env at the project root."
    )

_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.1,
    api_key=_api_key,
)


# ── structured output ─────────────────────────────────────────────────────────
class SecurityAlert(BaseModel):
    severity: Literal["Low", "Medium", "High"] = Field(
        description="Threat classification based on context and history."
    )
    summary: str = Field(
        description=(
            "3-5 sentence narrative: what happened, correlated history found, "
            "why this severity was chosen, and any pattern recognised from memory."
        )
    )
    target_interface: Literal["Resident", "Guard", "Supervisor"] = Field(
        description="Low → Resident. Medium → Guard. High → Supervisor."
    )
    recommended_action: str = Field(
        description="One concrete instruction for the receiving party."
    )
    trust_score_action: str = Field(
        description=(
            "Brief justification for the trust score penalty being applied "
            "to the responsible resident (if any). E.g. 'First offence, minor deduction.'"
        )
    )


_structured_llm = _llm.with_structured_output(SecurityAlert)

_SYSTEM_PROMPT = """You are Heimdall AI — a Tier-2 Physical Security Investigator.

Analyse the incoming anomaly context packet and produce a structured alert.

═══ SEVERITY RULES ═══
High   → Any DOOR_ALARM (physical forced entry);
         OR responsible user has ≥2 prior incidents in the 10-hour window;
         OR compound attack: tailgating + forced-open within 10 minutes of each other;
         OR trust_score < 0.50 (repeat offender with degraded trust).
Medium → Tailgating with 1 prior incident by same user in 10 hrs;
         OR tailgating by an unidentified / unauthenticated person;
         OR anomaly correlates with another anomaly at a different gate within 10 min.
Low    → First-time tailgating by a known resident, zero prior history, no correlations.

═══ TARGET INTERFACE ═══
Low    → Resident (push notification only)
Medium → Guard   (guard dashboard + resident app)
High   → Supervisor (supervisor dashboard + guard + resident)

═══ TRUST SCORE NOTE ═══
You will NOT compute the new trust score — the system does that automatically.
Instead, in trust_score_action, briefly justify why the penalty is fair given the context.

═══ EPISODIC MEMORY ═══
Your conversation memory may contain summaries of prior alerts in this session.
If you recognise a repeat pattern (same user, same gate, escalating behaviour),
call it out explicitly in your summary and escalate severity accordingly."""


# ═══════════════════════════════════════════════════════════════════════════════
# NODE: INVESTIGATE
# ═══════════════════════════════════════════════════════════════════════════════
def investigate_node(state: SecurityState) -> dict:
    """
    Pull the oldest anomaly from anomaly_queue (passed in via state),
    gather full context from DB, call Gemini, return updated state.
    """
    queue: list[dict] = list(state.get("anomaly_queue", []))
    if not queue:
        return {}

    incident    = queue.pop(0)
    signal_type = incident["signal_type"]
    gate_id     = incident["gate_id"]
    user_id     = incident.get("responsible_user_id")
    ts          = incident.get("timestamp", "")

    print(f"\n{'═'*70}")
    print(f"🔍 [INVESTIGATE] {signal_type} @ {gate_id}  |  user: {user_id or 'UNKNOWN'}")
    print(f"   Remaining in queue after this: {len(queue)}")

    # ── context aggregation ────────────────────────────────────────────────
    history     = database.get_recent_anomalies(gate_id, user_id, hours_back=10)
    correlation = database.get_cross_incident_correlation(ts, window_minutes=10)
    profile     = database.get_resident_full_profile(user_id) if user_id else None

    # derive quick stats for the prompt
    prior_tailgating_by_user = len(history.get("tailgating_by_user", []))
    prior_forced_at_gate     = len(history.get("forced_open_at_gate", []))
    correlated_other         = (
        len(correlation.get("correlated_tailgating", []))
        + len(correlation.get("correlated_forced_open", []))
    )
    trust_score = profile.get("trust_score", 1.0) if profile else None

    print(f"   📊 Prior tailgating (user, 10h): {prior_tailgating_by_user}")
    print(f"   📊 Prior forced-open (gate, 10h): {prior_forced_at_gate}")
    print(f"   📊 Correlated anomalies (±10min): {correlated_other}")
    print(f"   📊 Current trust score: {trust_score if trust_score is not None else 'N/A (no user)'}")

    context_packet = {
        "incident":             incident,
        "responsible_party":    profile or "No credential authentication trace found.",
        "db_history_last_10h":  history,
        "cross_incident_10min": correlation,
    }

    print("   🤖 Sending to Gemini 2.5 Flash...")
    result: SecurityAlert = _structured_llm.invoke(
        [
            SystemMessage(content=_SYSTEM_PROMPT),
            *state.get("messages", []),
            HumanMessage(
                content=(
                    "Analyse this context packet:\n\n"
                    + json.dumps(context_packet, default=str, indent=2)
                )
            ),
        ]
    )

    # ── terminal display ───────────────────────────────────────────────────
    emoji = {"Low": "🟡", "Medium": "🟠", "High": "🔴"}.get(result.severity, "⚪")
    print(f"\n  {'▓'*66}")
    print(f"  {emoji}  HEIMDALL ALERT  ──  [{result.severity.upper()}]")
    print(f"  Type     : {signal_type}")
    print(f"  Gate     : {gate_id}")
    print(f"  User     : {user_id or 'UNKNOWN'}")
    print(f"  Target   : {result.target_interface}")
    print(f"  Summary  : {result.summary}")
    print(f"  Action   : {result.recommended_action}")
    print(f"  Trust ⚖️  : {result.trust_score_action}")
    print(f"  {'▓'*66}\n")

    alert_dict = {
        "signal_type":        signal_type,
        "gate_id":            gate_id,
        "timestamp":          ts,
        "user_id":            user_id,
        "severity":           result.severity,
        "summary":            result.summary,
        "target_interface":   result.target_interface,
        "recommended_action": result.recommended_action,
        "trust_score_action": result.trust_score_action,
        "trust_score_before": trust_score,
    }

    existing = list(state.get("investigation_results", []))
    existing.append(alert_dict)

    # episodic memory — short entry for future cross-referencing
    memory_msg = HumanMessage(
        content=(
            f"[MEMORY] {result.severity} alert — {signal_type} at {gate_id} "
            f"by {user_id or 'Unknown'}. "
            f"Trust score was {trust_score}. {result.summary}"
        )
    )

    return {
        "anomaly_queue":         queue,
        "investigation_results": existing,
        "messages":              [memory_msg],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NODE: DISPATCH
# ═══════════════════════════════════════════════════════════════════════════════
def dispatch_node(state: SecurityState) -> dict:
    """
    Pop the oldest alert, apply the trust score penalty, save the report,
    and print the final dispatch line.
    """
    results: list[dict] = list(state.get("investigation_results", []))
    if not results:
        return {}

    alert   = results.pop(0)
    user_id = alert.get("user_id")

    # ── trust score update ─────────────────────────────────────────────────
    if user_id:
        ts_update = database.update_trust_score(user_id, alert["severity"])
        alert["trust_score_after"] = ts_update.get("new")
        alert["trust_score_delta"] = ts_update.get("delta")
        penalty_str = (
            f"  Trust score: {ts_update['old']} → {ts_update['new']}  "
            f"(Δ {ts_update['delta']:+.2f}  penalty for {alert['severity']} alert)"
        )
    else:
        alert["trust_score_after"] = None
        alert["trust_score_delta"] = None
        penalty_str = "  Trust score: N/A (no authenticated user)"

    # ── save to DB ─────────────────────────────────────────────────────────
    database.save_investigation_report(alert)

    # ── terminal dispatch block ────────────────────────────────────────────
    bar = {"Low": "▬▬▬▬▬", "Medium": "▬▬▬▬▬▬▬▬▬", "High": "▬▬▬▬▬▬▬▬▬▬▬▬▬"}.get(alert["severity"], "")
    print(f"\n📡 [DISPATCH] {'═'*54}")
    print(f"  SEVERITY   : {alert['severity']} {bar}")
    print(f"  TYPE       : {alert['signal_type']}")
    print(f"  GATE       : {alert['gate_id']}")
    print(f"  USER       : {user_id or 'UNKNOWN'}")
    print(f"  TIME       : {alert.get('timestamp','N/A')}")
    print(f"  TARGET UI  : {alert['target_interface']}")
    print(f"  SUMMARY    : {alert['summary']}")
    print(f"  ACTION     : {alert['recommended_action']}")
    print(penalty_str)
    print(f"  💾 Report saved to Investigation_Reports")
    print(f"  {'═'*56}\n")

    return {"investigation_results": results}
