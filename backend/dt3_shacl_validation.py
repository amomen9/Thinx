"""D-T3: Independent pre-upload SHACL validator.

Uses supplied SHACL shapes. Does not modify RDF,
the shared ontology, or AllegroGraph.
"""

from rdflib import Graph, Namespace
from rdflib.namespace import RDF
from pyshacl import validate

SH = Namespace("http://www.w3.org/ns/shacl#")


def validate_rdf(data_file, shapes_file):
    """Return a validation result. Fail closed on errors."""

    try:
        data_graph = Graph()
        data_graph.parse(data_file, format="turtle")

        shapes_graph = Graph()
        shapes_graph.parse(shapes_file, format="turtle")

        has_shapes = (
            any(shapes_graph.subjects(RDF.type, SH.NodeShape))
            or any(shapes_graph.subjects(RDF.type, SH.PropertyShape))
        )

        if not has_shapes:
            raise ValueError("No SHACL shapes found.")

        conforms, report_graph, _ = validate(
            data_graph=data_graph,
            shacl_graph=shapes_graph,
            inference="none",
            abort_on_first=False,
            allow_warnings=True,
            allow_infos=True,
            meta_shacl=True,
        )

        issues = []

        for result in report_graph.subjects(
            RDF.type, SH.ValidationResult
        ):
            message = report_graph.value(
                result, SH.resultMessage
            )
            focus = report_graph.value(
                result, SH.focusNode
            )
            path = report_graph.value(
                result, SH.resultPath
            )
            severity = report_graph.value(
                result, SH.resultSeverity
            )

            issues.append({
                "message": str(message or "Validation issue"),
                "focus_node": str(focus or ""),
                "property": str(path or ""),
                "severity": str(severity or SH.Violation),
            })

        return {
            "conforms": bool(conforms),
            "issues": issues,
            "error": None,
        }

    except Exception as exc:
        return {
            "conforms": False,
            "issues": [],
            "error": "Validation could not be completed: "
                     + str(exc),
        }
