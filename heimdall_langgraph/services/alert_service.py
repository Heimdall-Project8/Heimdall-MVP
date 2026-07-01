from datetime import datetime
import random
import uuid

import database


# ------------------------------------------------------
# Internal Helpers
# ------------------------------------------------------

def _get_available_guard():

    guards = database.get_all_guards()

    if not guards:
        return None

    # For hackathon:
    # Random guard assignment.
    # Later replace with least busy guard.
    return random.choice(guards)


def _status_for(severity):

    severity = severity.lower()

    if severity == "high":
        return "OPEN"

    if severity == "medium":
        return "PENDING_VERIFICATION"

    if severity == "low":
        return "NOTIFIED"

    return "SUPPRESSED"


# ------------------------------------------------------
# Main Routing
# ------------------------------------------------------

def route_alert(alert):

    severity = alert["severity"]

    document = {

        "alert_id": str(uuid.uuid4()),

        "incident_id": alert.get("incident_id"),

        "resident_id": alert.get("user_id"),

        "gate_id": alert.get("gate_id"),

        "signal_type": alert.get("signal_type"),

        "summary": alert.get("summary"),

        "recommended_action": alert.get("recommended_action"),

        "severity": severity,

        "status": _status_for(severity),

        "assigned_to": None,

        "assigned_guard": None,

        "verified": False,

        "resolved": False,

        "created_at": datetime.utcnow(),

        "updated_at": datetime.utcnow()

    }

    # ------------------------------------
    # LOW
    # ------------------------------------

    if severity == "Low":

        document["assigned_to"] = "resident"

    # ------------------------------------
    # MEDIUM
    # ------------------------------------

    elif severity == "Medium":

        guard = _get_available_guard()

        document["assigned_to"] = "guard"

        if guard:

            document["assigned_guard"] = guard["id"]

    # ------------------------------------
    # HIGH
    # ------------------------------------

    elif severity == "High":

        # High alerts first go to the admin.
        # Admin will manually assign a guard later.

        document["assigned_to"] = "admin"

        document["assigned_guard"] = None

        document["status"] = "OPEN"

    else:

        document["assigned_to"] = None

    database.save_alert(document)

    print("\n==============================")

    print("🚨 ALERT ROUTED")

    print("Severity :", severity)

    print("Recipient :", document["assigned_to"])

    if document["assigned_guard"]:

        print("Guard     :", document["assigned_guard"])

    else:

        print("Guard     : Waiting for admin assignment")

    print("==============================\n")

    return document


# ------------------------------------------------------
# Guard Actions
# ------------------------------------------------------

def verify_alert(alert_id):

    database.verify_alert(alert_id)


def resolve_alert(alert_id):

    database.resolve_alert(alert_id)


def assign_guard(alert_id, guard_id):

    database.assign_guard(

        alert_id,

        guard_id

    )