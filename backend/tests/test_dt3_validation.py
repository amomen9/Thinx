"""D-T3 independent SHACL and pre-upload gate tests.

Uses synthetic RDF, provisional namespaces, and a mock uploader.
No connections to AllegroGraph or the shared ETL.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dt3_shacl_validation import validate_rdf
from dt3_preupload_gate import (
    SHACLUploadBlocked,
    validate_then_upload,
)


SHAPES = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix thinx: <https://example.org/thinx#> .
@prefix hds: <http://example.org/hds#> .
@prefix schema: <http://schema.org/> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix dcterms: <http://purl.org/dc/terms/> .

thinx:EventShape a sh:NodeShape ;
    sh:targetClass thinx:TraffickingEvent ;
    sh:property [
        sh:path hds:involves ;
        sh:class prov:Agent ;
        sh:message "Involved actor must be an Agent."
    ] ;
    sh:property [
        sh:path schema:location ;
        sh:class dcterms:Location ;
        sh:message "Event location must be a Location."
    ] .
"""

VALID_RDF = """
@prefix thinx: <https://example.org/thinx#> .
@prefix hds: <http://example.org/hds#> .
@prefix schema: <http://schema.org/> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix dcterms: <http://purl.org/dc/terms/> .

<urn:case:1> a thinx:TraffickingEvent ;
    hds:involves <urn:actor:1> ;
    schema:location <urn:location:1> .

<urn:actor:1> a prov:Agent .
<urn:location:1> a dcterms:Location .
"""

INVALID_RDF = VALID_RDF.replace(
    "<urn:actor:1> a prov:Agent .",
    "<urn:actor:1> a dcterms:Location ."
).replace(
    "<urn:location:1> a dcterms:Location .",
    "<urn:location:1> a prov:Agent ."
)


class TestDT3Validation(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name)

        def save(name, content):
            path = folder / name
            path.write_text(content, encoding="utf-8")
            return str(path)

        self.shapes = save("shapes.ttl", SHAPES)
        self.valid = save("valid.ttl", VALID_RDF)
        self.invalid = save("invalid.ttl", INVALID_RDF)
        self.empty_shapes = save("empty.ttl", "")
        self.broken = save("broken.ttl", "INVALID RDF !!!")
        self.calls = []

    def mock_upload(self, path):
        self.calls.append(path)
        return "MOCK_UPLOAD_SUCCESS"

    def assert_upload_blocked(self, data, shapes):
        before = len(self.calls)

        with self.assertRaises(SHACLUploadBlocked):
            validate_then_upload(
                data, shapes, self.mock_upload
            )

        self.assertEqual(len(self.calls), before)

    def test_valid_rdf_accepted(self):
        result = validate_rdf(self.valid, self.shapes)
        self.assertTrue(result["conforms"], result)

    def test_invalid_relationships_rejected(self):
        result = validate_rdf(self.invalid, self.shapes)
        self.assertFalse(result["conforms"])
        self.assertGreaterEqual(len(result["issues"]), 2)

        messages = [i["message"] for i in result["issues"]]
        self.assertIn(
            "Involved actor must be an Agent.", messages
        )
        self.assertIn(
            "Event location must be a Location.", messages
        )

    def test_empty_shapes_rejected(self):
        result = validate_rdf(self.valid, self.empty_shapes)
        self.assertFalse(result["conforms"])
        self.assertIsNotNone(result["error"])

    def test_malformed_rdf_rejected(self):
        result = validate_rdf(self.broken, self.shapes)
        self.assertFalse(result["conforms"])
        self.assertIsNotNone(result["error"])

    def test_valid_rdf_upload_allowed(self):
        result = validate_then_upload(
            self.valid, self.shapes, self.mock_upload
        )
        self.assertEqual(result, "MOCK_UPLOAD_SUCCESS")
        self.assertEqual(self.calls, [self.valid])

    def test_invalid_rdf_upload_blocked(self):
        self.assert_upload_blocked(
            self.invalid, self.shapes
        )

    def test_empty_shapes_upload_blocked(self):
        self.assert_upload_blocked(
            self.valid, self.empty_shapes
        )

    def test_malformed_rdf_upload_blocked(self):
        self.assert_upload_blocked(
            self.broken, self.shapes
        )


if __name__ == "__main__":
    unittest.main()
