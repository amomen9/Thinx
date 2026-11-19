"""D-T2 draft value validation; no ETL or file modifications."""

ATTRIBUTE_TYPES = {
    "detention",
    "beating",
    "starvation",
    "forced labour",
    "sexual violence",
    "torture",
    "shooting",
    "tying",
    "phone confiscation",
}

INTERVIEWEE_TYPES = {
    "victim",
    "witness",
    "professional",
}

AGENT_ROLES = {
    "smuggler",
    "guard",
    "middleman",
    "unknown",
}

LOCATION_LEVELS = {
    "country",
    "region",
    "town",
}

LOCATION_ROLES = {
    "transit point",
    "interview place",
}

DATE_KINDS = {
    "event",
    "interview",
    "unknown",
}

ALLOWED_VALUES = {
    ("Attribute", "type"): ATTRIBUTE_TYPES,
    ("Interviewee", "type"): INTERVIEWEE_TYPES,
    ("Agent", "role"): AGENT_ROLES,
    ("Location", "level"): LOCATION_LEVELS,
    ("Location", "role"): LOCATION_ROLES,
    ("TraffickingEvent", "date_kind"): DATE_KINDS,
}


def normalize_value(value):
    """Normalize labels without changing source data."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A non-empty text value is required.")

    return " ".join(
        value.strip().casefold()
        .replace("_", " ")
        .replace("-", " ")
        .split()
    )


def validate_value(entity, field, value):
    """Validate one value against the draft vocabulary."""
    key = (entity, field)

    if key not in ALLOWED_VALUES:
        raise ValueError("No draft vocabulary for this field.")

    normalized = normalize_value(value)

    if normalized not in ALLOWED_VALUES[key]:
        raise ValueError(
            f"Invalid value for {entity}.{field}."
        )

    return normalized


def extract_yes_attributes(row, confirmed_columns):
    """
    Identify Attribute types marked yes.

    confirmed_columns maps source headers to Attribute types.
    This function does not create RDF or modify the dataset.
    """
    if not isinstance(row, dict):
        raise ValueError("A source record must be a dictionary.")

    if not isinstance(confirmed_columns, dict):
        raise ValueError("Confirmed columns must be a dictionary.")

    selected = []

    for source_column, attribute_type in confirmed_columns.items():
        category = validate_value(
            "Attribute", "type", attribute_type
        )

        if source_column not in row:
            raise ValueError("Confirmed source column is missing.")

        value = row[source_column]

        if value is None:
            flag = ""
        elif isinstance(value, str):
            flag = value.strip().casefold()
        else:
            raise ValueError(
                "Attribute flag must be yes, no, or empty."
            )

        if flag == "yes":
            selected.append(category)
        elif flag in ("no", "", "unknown"):
            continue
        else:
            raise ValueError(
                "Unexpected Attribute flag value."
            )

    return selected


def resolve_event_date(event_date, interview_date, interview_date_approved=False):
    """Choose a date with explicit stand-in provenance."""
    for value in (event_date, interview_date):
        if value is not None and not isinstance(value, str):
            raise ValueError("Dates must be text or None.")

    if event_date and event_date.strip():
        return {"date": event_date.strip(), "date_kind": "event"}

    if interview_date and interview_date.strip():
        if interview_date_approved is not True:
            raise ValueError("Interview date stand-in requires approval.")
        return {"date": interview_date.strip(), "date_kind": "interview"}

    return {"date": None, "date_kind": "unknown"}


def preserve_ransom_amount(value):
    """Preserve original ransom amounts, including ranges."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("Invalid ransom amount.")

    text = str(value).strip()
    return text or None
