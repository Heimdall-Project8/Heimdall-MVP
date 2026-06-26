# 🛡️ Heimdall v2 — LangGraph Security AI Pipeline

## Key architecture change vs v1

```
v1: simulate → detect → investigate → dispatch   (single thread, LLM blocks simulator)
v2: simulator thread  ║  investigate → dispatch  (parallel — simulator never stops)
```

The simulator runs in a **background daemon thread** continuously writing events to a `queue.Queue`.  
The LangGraph investigation loop polls that queue and processes anomalies in FIFO order.  
LLM inference never pauses event generation.

---

## Folder structure

```
project_root/
├── heimdall_security_residents_actual.csv   ← resident roster
├── .env                                      ← MONGO_URI + GEMINI_API_KEY
└── heimdall_langgraph/
    ├── graph.py         ← entry point, polling loop, graph wiring
    ├── simulator.py     ← background thread: event gen + Tier-1 detector
    ├── nodes.py         ← investigate_node + dispatch_node (LLM brain)
    ├── database.py      ← MongoDB + CSV helpers, trust score mutations
    ├── state.py         ← SecurityState TypedDict
    └── requirements.txt
```

---

## Setup & run

```bash
pip install -r requirements.txt
python graph.py
```

**.env** (at project root, one level above this folder):
```
MONGO_URI=mongodb+srv://...
GEMINI_API_KEY=your_key
HEIMDALL_TICK_SLEEP=0.6      # seconds between sim ticks (lower = faster)
HEIMDALL_POLL_INTERVAL=0.5   # seconds between queue polls in main loop
```

---

## Trust score system

Stored on each resident document in the MongoDB `residents` collection.  
Initialised at **1.0** on first encounter.

| Alert severity | Penalty | Example: score before → after |
|---|---|---|
| Low    | −0.02 | 1.00 → 0.98 |
| Medium | −0.05 | 0.98 → 0.93 |
| High   | −0.10 | 0.93 → 0.83 |

Floor: **0.0** (never goes negative).  
A trust_score < 0.50 causes the LLM to automatically escalate to **High** severity.

---

## MongoDB collections

| Collection | Written by | Content |
|---|---|---|
| `Tailgating_incidents` | simulator thread (Tier-1) | raw anomaly signals |
| `Door_Forced_Open_Incidents` | simulator thread (Tier-1) | raw anomaly signals |
| `residents` | dispatch_node | trust_score field, last_updated |
| `Investigation_Reports` | dispatch_node | full alert with LLM output + trust delta |

---

## Anomaly probability

| Event type | Probability | Approx rate |
|---|---|---|
| Normal entry | 90% | ~18 per 20 ticks |
| Tailgating   |  7% | ~1-2 per 20 ticks |
| Forced open  |  3% | ~1 per 33 ticks |

---

## Terminal output anatomy

```
┌─ [SIM tick 0023] ⚠️  TAILGATE                     ← simulator thread
  ⚙️  [14:32:07] north_gate    badge_swipe    → status:success, user_id:RES_042
  ⚙️  [14:32:08] north_gate    door_state_change → state:open
  ⚙️  [14:32:14] north_gate    person_counter_update → count:2
│  🚨 ANOMALY DETECTED → TAILGATING at north_gate | user: RES_042
│  💾 Saved to DB  (id: 64ab...)
│  📥 Pushed to investigation queue  (depth now: 1)
└─ queue depth: 1

⚡ [MAIN LOOP] Anomaly pulled from queue              ← main polling loop

═══════════════════════════════════════════════════
🔍 [INVESTIGATE] TAILGATING @ north_gate | user: RES_042
   📊 Prior tailgating (user, 10h): 1
   📊 Current trust score: 0.98
   🤖 Sending to Gemini 2.5 Flash...

  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
  🟠  HEIMDALL ALERT  ──  [MEDIUM]
  Summary  : Resident RES_042 has 1 prior tailgating in the last 10 hours...
  Target   : Guard
  Action   : Dispatch guard to north_gate immediately.
  Trust ⚖️  : Second offence within 10 hours warrants a medium penalty.
  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓

📡 [DISPATCH]
  SEVERITY : Medium
  Trust score: 0.98 → 0.93  (Δ -0.05)
  💾 Report saved to Investigation_Reports
```
