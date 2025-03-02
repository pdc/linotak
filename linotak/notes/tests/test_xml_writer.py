from io import BytesIO

from django.test import TestCase

from ...xml_writer import Document


class TestDocument(TestCase):
    def test_can_write_empty_feed(self):
        doc = Document(
            "atom:feed", prefix_namespaces={"atom": "http://www.w3.org/2005/Atom"}
        )

        buf = BytesIO()
        doc.write_to(buf)
        result = buf.getvalue().decode("UTF-8")

        self.assertEqual(
            result,
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<atom:feed xmlns:atom="http://www.w3.org/2005/Atom"/>',
        )

    def test_can_xml_lang_attributes(self):
        doc = Document(
            "atom:feed",
            {"xml:lang": "en-GB"},
            prefix_namespaces={"atom": "http://www.w3.org/2005/Atom"},
        )

        buf = BytesIO()
        doc.write_to(buf)
        result = buf.getvalue().decode("UTF-8")

        self.assertEqual(
            result,
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<atom:feed xmlns:atom="http://www.w3.org/2005/Atom" xml:lang="en-GB"/>',
        )

    def test_can_write_scalar_element(self):
        doc = Document(
            "atom:feed",
            {"xml:lang": "en-GB"},
            prefix_namespaces={"atom": "http://www.w3.org/2005/Atom"},
        )
        doc.add_child("atom:title", {}, "The Title")

        buf = BytesIO()
        doc.write_to(buf)
        result = buf.getvalue().decode("UTF-8")

        self.assertEqual(
            result,
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<atom:feed xmlns:atom="http://www.w3.org/2005/Atom" xml:lang="en-GB">\n'
            "    <atom:title>The Title</atom:title>\n"
            "</atom:feed>",
        )

    def test_can_write_nested_element(self):
        doc = Document(
            "atom:feed",
            {"xml:lang": "en-GB"},
            prefix_namespaces={"atom": "http://www.w3.org/2005/Atom"},
        )
        doc.add_child("atom:entry").add_child("atom:id", {}, "urn:foo:bar")

        buf = BytesIO()
        doc.write_to(buf)
        result = buf.getvalue().decode("UTF-8")

        self.assertEqual(
            result,
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<atom:feed xmlns:atom="http://www.w3.org/2005/Atom" xml:lang="en-GB">\n'
            "    <atom:entry>\n"
            "        <atom:id>urn:foo:bar</atom:id>\n"
            "    </atom:entry>\n"
            "</atom:feed>",
        )

    def test_can_use_default_namespace(self):
        doc = Document(
            "feed",
            {"xml:lang": "en-GB"},
            prefix_namespaces={"": "http://www.w3.org/2005/Atom"},
        )
        doc.add_child("entry").add_child("id", {}, "urn:foo:bar")

        buf = BytesIO()
        doc.write_to(buf)
        result = buf.getvalue().decode("UTF-8")

        self.assertEqual(
            result,
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="en-GB">\n'
            "    <entry>\n"
            "        <id>urn:foo:bar</id>\n"
            "    </entry>\n"
            "</feed>",
        )
