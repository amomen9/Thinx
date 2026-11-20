"""D-T3 severity tests with synthetic RDF and SHACL shapes."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dt3_shacl_validation import validate_rdf
from dt3_preupload_gate import (
    validate_then_upload,
    SHACLUploadBlocked,
)


DATA = """
@prefix ex: <https://example.org/test#> .

ex:event1 a ex:Event ;
    ex:actor ex:actor1 .

ex:actor1 a ex:OtherClass .
"""


def make_shapes(severity):
    return """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <https://example.org/test#> .

ex:EventShape a sh:NodeShape ;
    sh:targetClass ex:Event ;
    sh:property [
        sh:path ex:actor ;
        sh:class ex:Agent ;
        sh:severity sh:%s ;
        sh:message "Actor has the wrong class."
    ] .
""" % severity


class TestDT3Severity(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.calls = []

    def save(self, name, content):
        path = self.folder / name
        path.write_text(content, encoding="utf-8")
        return str(path)

    def mock_upload(self, path):
        self.calls.append(path)
        return "MOCK_UPLOAD_SUCCESS"

    def test_warning_is_reported_without_blocking(self):
        data = self.save("data.ttl", DATA)
        shapes = self.save(
            "warning.ttl", make_shapes("Warning")
        )

        result = validate_rdf(data, shapes)

        self.assertTrue(result["conforms"], result)
        self.assertIsNone(result["error"])
        self.assertGreaterEqual(len(result["issues"]), 1)
        self.assertTrue(any(
            issue["severity"].endswith("#Warning")
            for issue in result["issues"]
        ))

    def test_warning_allows_mock_upload(self):
        data = self.save("data.ttl", DATA)
        shapes = self.save(
            "warning.ttl", make_shapes("Warning")
        )

        output = validate_then_upload(
            data, shapes, self.mock_upload
        )

        self.assertEqual(output, "MOCK_UPLOAD_SUCCESS")
        self.assertEqual(self.calls, [data])

    def test_violation_blocks_mock_upload(self):
        data = self.save("data.ttl", DATA)
        shapes = self.save(
            "violation.ttl", make_shapes("Violation")
        )

        result = validate_rdf(data, shapes)

        self.assertFalse(result["conforms"])
        self.assertTrue(any(
            issue["severity"].endswith("#Violation")
            for issue in result["issues"]
        ))

        with self.assertRaises(SHACLUploadBlocked):
            validate_then_upload(
                data, shapes, self.mock_upload
            )

        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
