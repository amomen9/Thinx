
"""D-T2: Record researcher-approved mapping decisions."""

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


RUNS_DIR = Path("/workspace/dt2_runs")


def save_mapping_decision(
    mapping,
    date_kind,
    researcher_approved,
    interview_date_approved,
    source_filename
):
    """Save metadata for a successfully applied mapping."""

    if researcher_approved is not True:
        raise ValueError("Researcher mapping approval is required.")

    if date_kind not in ("event", "interview", "unknown"):
        raise ValueError("Invalid date_kind.")

    if date_kind == "interview" and interview_date_approved is not True:
        raise ValueError("Interview-date approval is required.")

    if not isinstance(mapping, dict) or not mapping:
        raise ValueError("A valid mapping is required.")

    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    record_id = str(uuid4())

    record = {
        "record_id": record_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_file": Path(source_filename).name,
        "mapping": mapping,
        "researcher_approved": researcher_approved,
        "date_kind": date_kind,
        "interview_date_approved": (
            interview_date_approved if date_kind == "interview" else False
        ),
        "status": "mapping_applied"
    }

    record_path = RUNS_DIR / f"{record_id}.json"
    temp_path = RUNS_DIR / f".{record_id}.tmp"
    try:
        # Write the record completely before publishing it.
        with temp_path.open("x", encoding="utf-8") as file:
            json.dump(record, file, indent=2)
        temp_path.replace(record_path)
    finally:
        # Remove incomplete temporary records after a failure.
        temp_path.unlink(missing_ok=True)

    return record_id
def apply_with_decision_record(
    source_path,
    write_staged_file,
    mapping,
    date_kind,
    researcher_approved,
    interview_date_approved
):
    """Apply a staged mapping and save its decision record."""

    import os
    import shutil

    source_path = Path(source_path)
    token = uuid4().hex

    # Keep Excel extension for pandas; avoid .json in uploads.
    suffix = ".xlsx" if source_path.suffix.lower() == ".xlsx" else ".staged"

    staged_path = source_path.with_name(f".dt2-{token}{suffix}")
    backup_path = source_path.with_name(f".dt2-{token}.backup")

    replaced = False
    rollback_succeeded = True

    try:
        # Prepare the updated dataset without changing the original.
        write_staged_file(staged_path)

        # Preserve the original before replacing it.
        shutil.copy2(source_path, backup_path)
        os.replace(staged_path, source_path)
        replaced = True

        # Record the approved decision.
        record_id = save_mapping_decision(
            mapping,
            date_kind,
            researcher_approved,
            interview_date_approved,
            source_path.name
        )

        return record_id

    except Exception:
        if replaced:
            try:
                os.replace(backup_path, source_path)
            except OSError:
                rollback_succeeded = False
        raise

    finally:
        if staged_path.exists():
            staged_path.unlink()

        # Preserve the backup if rollback was unsuccessful.
        if rollback_succeeded and backup_path.exists():
            backup_path.unlink()
