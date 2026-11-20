"""D-T3: Block RDF publication when SHACL validation fails.

Standalone integration helper. Not yet connected to the
shared ETL or AllegroGraph.
"""

from dt3_shacl_validation import validate_rdf


class SHACLUploadBlocked(RuntimeError):
    """Raised when RDF is not safe to publish."""

    def __init__(self, validation_result):
        self.validation_result = validation_result

        messages = [
            issue["message"]
            for issue in validation_result.get("issues", [])
        ]

        reason = (
            validation_result.get("error")
            or "; ".join(messages)
            or "RDF failed SHACL validation."
        )

        super().__init__("Upload blocked: " + reason)


def validate_then_upload(data_file, shapes_file, upload_function):
    """Validate RDF before invoking the supplied uploader."""

    result = validate_rdf(data_file, shapes_file)

    if not result["conforms"]:
        raise SHACLUploadBlocked(result)

    return upload_function(data_file)
