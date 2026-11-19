"""D-T2 draft vocabulary alignment with HDS MIP v2.

Compact RDF terms only. Does not generate RDF, modify the
shared ontology, or change existing mapping behavior.
"""

from dt2_schema_draft import DRAFT_CDM_SCHEMA


# Proposed RDF classes.
CLASS_TERMS = {
    "TraffickingEvent": "thinx:TraffickingEvent",
    "Location": "dcterms:Location",
    "Attribute": "skos:Concept",
    "Agent": "prov:Agent",
    "Ransom": "thinx:Ransom",
    "Interviewee": "prov:Agent",
}

# The HDS superclass of the Thinx-specific event class.
EVENT_SUPERCLASS = "hds:Incident"

# Proposed relationships from TraffickingEvent.
EVENT_RELATIONS = {
    "Location": "schema:location",
    "Attribute": "thinx:coercion",
    "Agent": "hds:involves",
    "Ransom": "thinx:ransom",
    "Interviewee": "hds:reportedBy",
}

# Field-to-property correspondences supported by the draft.
FIELD_TERMS = {
    "TraffickingEvent.date": "schema:startDate",
    "TraffickingEvent.date_kind": "thinx:dateKind",
    "Location.name": "rdfs:label",
    "Agent.role": "hds:actorType",
}


def describe_target(target):
    """Describe a confirmed CDM target without generating RDF."""

    if not isinstance(target, str) or "." not in target:
        raise ValueError("Invalid CDM target.")

    entity, field = target.split(".", 1)

    if entity not in DRAFT_CDM_SCHEMA:
        raise ValueError("Unknown CDM class.")

    valid_fields = {
        item["name"]
        for item in DRAFT_CDM_SCHEMA[entity]["fields"]
    }

    if field not in valid_fields:
        raise ValueError("Unknown CDM field.")

    return {
        "internal_target": target,
        "rdf_class": CLASS_TERMS[entity],
        "rdf_property": FIELD_TERMS.get(target),
        "event_relation": EVENT_RELATIONS.get(entity),
        "property_pending": target not in FIELD_TERMS,
    }


def describe_mapping(mapping):
    """Translate proposed or approved mapping targets to HDS metadata."""

    if not isinstance(mapping, dict):
        raise ValueError("Mapping must be a dictionary.")

    return {
        source: describe_target(target)
        for source, target in mapping.items()
        if target
    }
