from django.test import TestCase

from ..prescan import determine_encoding, get_attribute, normalize_encoding


class TestPrescan(TestCase):
    def test_simple(self):
        input = b"<!DOCTYPE html>\n<html lang=en>\n<head>\n<meta charset=UTF-8>\n"
        encoding, certainty = determine_encoding(input)

        self.assertEqual(encoding, "UTF-8")
        self.assertTrue(certainty)

    def test_pragma(self):
        input = b'<head>\n<meta content="text/html; charset=UTF-8" http-equiv="content-type">\n'
        encoding, certainty = determine_encoding(input)

        self.assertEqual(encoding, "UTF-8")
        self.assertTrue(certainty)


class TestGetAttribute(TestCase):

    def test_consumes_final_endtag(self):
        input = b"<meta/>"

        self.assertEqual(get_attribute(input, 5), (None, None, 7))

    def test_scans_attribute_sans_quotes(self):
        input = b"<meta foo=bar>"

        self.assertEqual(get_attribute(input, 6), (b"foo", b"bar", 13))

    def test_scans_attribute_with_single_quotes(self):
        input = b"<meta foo='bar'>"

        self.assertEqual(get_attribute(input, 6), (b"foo", b"bar", 15))

    def test_scans_attribute_with_double_quotes(self):
        input = b'<meta foo="bar"/>'

        self.assertEqual(get_attribute(input, 6), (b"foo", b"bar", 15))

    def test_scans_attribute_without_value(self):
        input = b"<meta foo>"

        self.assertEqual(get_attribute(input, 6), (b"foo", b"", 9))

    def test_scans_attribute_with_equal_without_value(self):
        input = b"<meta foo=>"

        self.assertEqual(get_attribute(input, 6), (b"foo", b"", 10))

    def test_scans_attribute_with_spaces(self):
        input = b"<meta\t\n  foo = 'bar'  baz = quux/quux2 />"

        self.assertEqual(get_attribute(input, 6), (b"foo", b"bar", 20))
        self.assertEqual(get_attribute(input, 20), (b"baz", b"quux/quux2", 38))

    def test_downcases_attrs_and_values(self):
        input = b'<meta CHARSET="UTF-8"/>'

        self.assertEqual(get_attribute(input, 6), (b"charset", b"utf-8", 21))


class TestNormalizeEncoding(TestCase):

    def test_utf_8_is_utf_8(self):
        self.assertEqual(normalize_encoding(b"UTF-8"), "UTF-8")
        self.assertEqual(normalize_encoding(b"utf-8"), "UTF-8")
        self.assertEqual(normalize_encoding(b"utf8"), "UTF-8")

    def test_alas_windows_1252_supersets_iso_8859_1_and_ascii(self):
        self.assertEqual(normalize_encoding(b"ISO-8859-1"), "windows-1252")
        self.assertEqual(normalize_encoding(b"ISO8859-1"), "windows-1252")
        self.assertEqual(normalize_encoding(b"ascii"), "windows-1252")
        self.assertEqual(normalize_encoding(b"us-ascii"), "windows-1252")
