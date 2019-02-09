"""Test for TagFilter et al."""

from django.test import TestCase
from unittest.mock import MagicMock

from ..tag_filter import TagFilter
from ..templatetags.note_lists import note_list_url
from .factories import SeriesFactory


class TestNoteListUrl(TestCase):

    def test_can_link_to_fully_specified_list(self):
        result = note_list_url(
            {},
            series=SeriesFactory.create(name='zerg'),
            tag_filter=TagFilter.parse('foo+bar'),
            drafts=True,
            page=13)

        self.assertEqual(result, '/zerg/tagged/bar+foo/drafts/page/13/')

    def test_omits_page_if_equal_to_1(self):
        result = note_list_url(
            {},
            series=SeriesFactory.create(name='zerg'),
            tag_filter=TagFilter.parse('foo+bar'),
            drafts=True,
            page=1)

        self.assertEqual(result, '/zerg/tagged/bar+foo/drafts/')

    def test_omits_drafts_if_false(self):
        result = note_list_url(
            {},
            series=SeriesFactory.create(name='zerg'),
            tag_filter=TagFilter.parse('foo+bar'),
            drafts=False,
            page=10)

        self.assertEqual(result, '/zerg/tagged/bar+foo/page/10/')

    def test_omits_tag_filter_if_false(self):
        result = note_list_url(
            {},
            series=SeriesFactory.create(name='zerg'),
            tag_filter=TagFilter(),
            drafts=False,
            page=10)

        self.assertEqual(result, '/zerg/page/10/')

    def test_omits_tag_filter_if_omitted(self):
        result = note_list_url(
            {},
            series=SeriesFactory.create(name='zerg'),
            tag_filter=None,
            drafts=False,
            page=10)

        self.assertEqual(result, '/zerg/page/10/')

    def test_shows_just_the_series_if_page_1(self):
        result = note_list_url(
            {},
            series=SeriesFactory.create(name='zerg'),
            tag_filter=None,
            drafts=False,
            page=1)

        self.assertEqual(result, '/zerg/')

    def test_shows_just_the_series_if_no_page(self):
        result = note_list_url(
            {},
            series=SeriesFactory.create(name='zerg'),
            tag_filter=None,
            drafts=False,
            page=None)

        self.assertEqual(result, '/zerg/')

    def test_uses_a_star_for_all_series(self):
        result = note_list_url(
            {},
            series=None,
            tag_filter=TagFilter(['wat']),
            drafts=False,
            page=69)

        self.assertEqual(result, '/*/tagged/wat/page/69/')

    def test_aquires_arguments_from_context(self):
        result = note_list_url(
            {
                'series': SeriesFactory.create(name='spof'),
                'tag_filter': TagFilter.parse('-sad'),
                'drafts': True,
                'page_obj': MagicMock(number=42)
            },
        )

        self.assertEqual(result, '/spof/tagged/-sad/drafts/page/42/')

    def test_gives_priority_to_args(self):
        result = note_list_url(
            {
                'series': SeriesFactory.create(name='spof'),
                'tag_filter': TagFilter.parse('-sad'),
                'drafts': True,
                'page_obj': MagicMock(number=42)
            },
            series='*',
            tag_filter=TagFilter(),
            drafts=False,
            page=41,
        )

        self.assertEqual(result, '/*/page/41/')
