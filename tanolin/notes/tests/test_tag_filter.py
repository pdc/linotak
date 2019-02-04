"""Test for TagFilter et al."""

from django.test import TestCase
from unittest.mock import MagicMock

from ..tag_filter import canonicalize_tag_name, wordify, TagFilter
from ..templatetags.tag_filters import with_included
from .factories import TagFactory


class TestCanonicalizeTagName(TestCase):

    def test_rejects_empty_label(self):
        with self.assertRaises(ValueError):
            canonicalize_tag_name('')

    def test_rejects_no_label(self):
        with self.assertRaises(ValueError):
            canonicalize_tag_name(None)

    def test_lowercases(self):
        self.assertEqual(canonicalize_tag_name('Foo'), 'foo')
        self.assertEqual(canonicalize_tag_name('FOO'), 'foo')
        self.assertEqual(canonicalize_tag_name('foo'), 'foo')

    def test_does_not_split_words(self):
        self.assertEqual(canonicalize_tag_name('FooBarBaz'), 'foobarbaz')


class TestWordify(TestCase):

    def test_spolits_camel_case(self):
        self.assertEqual(wordify('fooBarBaz'), 'foo bar baz')

    def test_leaves_initial_caps_if_first_letter_uppercase(self):
        self.assertEqual(wordify('FooBarBaz'), 'Foo Bar Baz')

    def test_leaves_allcaps_allcaps(self):
        self.assertEqual(wordify('FOOBarBaz'), 'FOO Bar Baz')
        self.assertEqual(wordify('FooBARBaz'), 'Foo BAR Baz')
        self.assertEqual(wordify('FooBarBAZ'), 'Foo Bar BAZ')
        self.assertEqual(wordify('fooBARBaz'), 'foo BAR baz')


class TestTagFilterParse(TestCase):

    def test_is_none_if_empty(self):
        self.assertIsNone(TagFilter.parse(''))
        self.assertIsNone(TagFilter.parse(None))

    def test_is_single_include_if_one_word(self):
        result = TagFilter.parse('foo')
        self.assertEqual(result, TagFilter(['foo']))

    def test_is_multiple_includes_if_multi_plus(self):
        result = TagFilter.parse('foo+bar+baz')
        self.assertEqual(result, TagFilter(['foo', 'bar', 'baz']))

    def test_ignores_order(self):
        one = TagFilter.parse('foo+bar+baz')
        two = TagFilter.parse('baz+foo+bar')
        self.assertEqual(one, two)

    def test_can_append_excluded_tags(self):
        result = TagFilter.parse('foo+bar-baz-quux')
        self.assertEqual(result, TagFilter(['bar', 'foo'], ['quux', 'baz']))

    def test_can_specify_single_excluded_tag(self):
        result = TagFilter.parse('-quux')
        self.assertEqual(result, TagFilter([], ['quux']))

    def test_can_unparse(self):
        self.assertEqual(TagFilter(['foo']).unparse(), 'foo')
        self.assertEqual(TagFilter(['foo', 'bar']).unparse(), 'bar+foo')
        self.assertEqual(TagFilter(['foo'], ['quux', 'bar']).unparse(), 'foo-bar-quux')


class TestTagFilterApply(TestCase):

    def test_can_filter_by_single_tag(self):
        queryset = MagicMock()
        queryset.filter.return_value = '*QUERYSET*'

        result = TagFilter(['foo']).apply(queryset)

        queryset.filter.assert_called_with(tags__name='foo')
        self.assertEqual(result, '*QUERYSET*')

    def test_can_filter_by_multiple_tags(self):
        queryset = MagicMock()
        queryset.filter.return_value.filter.return_value = '*QUERYSET*'

        result = TagFilter(['foo', 'bar']).apply(queryset)

        queryset.filter.assert_called_with(tags__name='bar')
        queryset.filter.return_value.filter.assert_called_with(tags__name='foo')
        self.assertEqual(result, '*QUERYSET*')

    def test_can_filter_out_multiple_tags(self):
        queryset = MagicMock()
        queryset.exclude.return_value.exclude.return_value = '*QUERYSET*'

        result = TagFilter([], ['foo', 'bar']).apply(queryset)

        queryset.exclude.assert_called_with(tags__name='bar')
        queryset.exclude.return_value.exclude.assert_called_with(tags__name='foo')
        self.assertEqual(result, '*QUERYSET*')


class TestTagFiltersWithIncluded(TestCase):

    def test_creates_new_tag_filter_if_fed_nothing(self):
        result = with_included(None, 'foo')

        self.assertEqual(result, TagFilter(['foo']))

    def test_adds_tag_to_filter(self):
        result = with_included(TagFilter(['foo'], ['quux']), 'bar')

        self.assertEqual(result, TagFilter(['foo', 'bar'], ['quux']))

    def test_ignores_redundant_tag(self):
        result = with_included(TagFilter(['foo']), 'foo')

        self.assertEqual(result, TagFilter(['foo']))

    def test_gets_name_from_tag(self):
        result = with_included(TagFilter(['foo']), TagFactory(name='bar'))

        self.assertEqual(result, TagFilter(['foo', 'bar']))
