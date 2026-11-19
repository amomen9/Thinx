"""
D-T2 draft schema for researcher confirmation testing.

Based on the proposed six-class structure.
Not yet integrated into the shared ontology or Ali's ETL.
"""

def make_class(description, field_names):
    return {
        "description": description,
        "fields": [
            {
                "name": name,
                "type": "string",
                "required": name == "id",
                "sensitive": False,
                "gdpr_category": None,
                "description": f"Draft field: {name}"
            }
            for name in field_names
        ]
    }


DRAFT_CDM_SCHEMA = {
    "TraffickingEvent": make_class(
        "One trafficking event associated with a case",
        ["id", "case_id", "date", "date_kind"]
    ),

    "Location": make_class(
        "A location associated with an event",
        ["id", "name", "level", "role"]
    ),

    "Attribute": make_class(
        "An event attribute such as beating or detention",
        ["id", "type"]
    ),

    "Agent": make_class(
        "An actor involved in the event",
        ["id", "role", "alias", "contact_tool"]
    ),

    "Ransom": make_class(
        "Ransom information associated with an event",
        ["id", "amount", "currency", "payment_method"]
    ),

    "Interviewee": make_class(
        "A victim, witness, or professional interviewee",
        ["id", "type"]
    )
}

# Draft date semantics; enforcement will be added separately.
DRAFT_CDM_SCHEMA["TraffickingEvent"]["fields"][3].update({
    "default": "unknown",
    "allowed_values": ["event", "interview", "unknown"]
})