"""Test for TagFilter et al."""

from django.test import TestCase, override_settings
from unittest.mock import MagicMock

from ..tag_filter import TagFilter
from ..templatetags.note_lists import note_list_url, note_url, profile_url
from .factories import SeriesFactory, NoteFactory, PersonFactory


@override_settings(NOTES_DOMAIN='example.org')
class TestNoteListUrl(TestCase):

    def test_can_link_to_fully_specified_list(self):
        result = note_list_url(
            {},
            series=SeriesFactory.create(name='zerg'),
            tag_filter=TagFilter.parse('foo+bar'),
            drafts=True,
            page=13)

        self.assertEqual(result, 'https://zerg.example.org/tagged/bar+foo/drafts/page13/')

    def test_omits_domain_if_same_as_series(self):
        zerg = SeriesFactory.create(name='zerg')
        result = note_list_url(
            {'series': zerg},
            series=zerg,
            tag_filter=TagFilter.parse('foo+bar'),
            drafts=True,
            page=13)

        self.assertEqual(result, '/tagged/bar+foo/drafts/page13/')

    def test_omits_page_if_equal_to_1(self):
        result = note_list_url(
            {},
            series=SeriesFactory.create(name='zerg'),
            tag_filter=TagFilter.parse('foo+bar'),
            drafts=True,
            page=1)

        self.assertEqual(result, 'https://zerg.example.org/tagged/bar+foo/drafts/')

    def test_omits_drafts_if_false(self):
        result = note_list_url(
            {},
            series=SeriesFactory.create(name='zerg'),
            tag_filter=TagFilter.parse('foo+bar'),
            drafts=False,
            page=10)

        self.assertEqual(result, 'https://zerg.example.org/tagged/bar+foo/page10/')

    def test_omits_tag_filter_if_false(self):
        result = note_list_url(
            {},
            series=SeriesFactory.create(name='zerg'),
            tag_filter=TagFilter(),
            drafts=False,
            page=10)

        self.assertEqual(result, 'https://zerg.example.org/page10/')

    def test_omits_tag_filter_if_omitted(self):
        result = note_list_url(
            {},
            series=SeriesFactory.create(name='zerg'),
            tag_filter=None,
            drafts=False,
            page=10)

        self.assertEqual(result, 'https://zerg.example.org/page10/')

    def test_shows_just_the_series_if_page_1(self):
        result = note_list_url(
            {},
            series=SeriesFactory.create(name='zerg'),
            tag_filter=None,
            drafts=False,
            page=1)

        self.assertEqual(result, 'https://zerg.example.org/')

    def test_shows_just_the_series_if_no_page(self):
        result = note_list_url(
            {},
            series=SeriesFactory.create(name='zerg'),
            tag_filter=None,
            drafts=False,
            page=None)

        self.assertEqual(result, 'https://zerg.example.org/')

    def test_root_if_same_series_and_if_page_1(self):
        result = note_list_url(
            {'series': SeriesFactory.create(name='zerg')},
            tag_filter=None,
            drafts=False,
            page=1)

        self.assertEqual(result, '/')

    def xtest_uses_a_star_for_all_series(self):
        result = note_list_url(
            {},
            series=None,
            tag_filter=TagFilter(['wat']),
            drafts=False,
            page=69)

        self.assertEqual(result, 'https://example.org/*/tagged/wat/page69/')

    def test_aquires_arguments_from_context(self):
        result = note_list_url(
            {
                'series': SeriesFactory.create(name='spof'),
                'tag_filter': TagFilter.parse('-sad'),
                'drafts': True,
                'page_obj': MagicMock(number=42)
            },
        )

        self.assertEqual(result, '/tagged/-sad/drafts/page42/')

    def test_gives_priority_to_args(self):
        result = note_list_url(
            {
                'series': SeriesFactory.create(name='spof'),
                'tag_filter': TagFilter.parse('-sad'),
                'drafts': True,
                'page_obj': MagicMock(number=42)
            },
            series=SeriesFactory.create(name='glog'),
            tag_filter=TagFilter(),
            drafts=False,
            page=41,
        )

        self.assertEqual(result, 'https://glog.example.org/page41/')

    def test_can_specify_view_in_which_case_tags_and_draft_ignored(self):
        result = note_list_url(
            {
                'series': SeriesFactory.create(name='spof'),
                'tag_filter': TagFilter.parse('-sad'),
                'drafts': True,
                'page_obj': MagicMock(number=42)
            },
            'new',
            series=SeriesFactory.create(name='zerg'),
        )

        self.assertEqual(result, 'https://zerg.example.org/new')

    def test_can_specify_feed(self):
        result = note_list_url(
            {
                'series': SeriesFactory.create(name='spof'),
                'tag_filter': TagFilter.parse('-sad'),
                'drafts': False,
                'page_obj': MagicMock(number=42)
            },
            'feed',
        )

        self.assertEqual(result, '/tagged/-sad/atom/')


@override_settings(NOTES_DOMAIN='example.org')
class TestNoteUrl(TestCase):

    def test_can_link_to_fully_specified_note(self):
        result = note_url(
            {},
            note=NoteFactory(series=SeriesFactory.create(name='zerg'), pk=69),
            tag_filter=TagFilter.parse('foo+bar'),
            drafts=True)

        self.assertEqual(result, 'https://zerg.example.org/tagged/bar+foo/drafts/69')

    def test_can_pass_view_name(self):
        result = note_url(
            {},
            'edit',
            note=NoteFactory(series=SeriesFactory.create(name='zerg'), pk=69),
            tag_filter=TagFilter.parse('foo+bar'),
            drafts=True)

        self.assertEqual(result, 'https://zerg.example.org/tagged/bar+foo/drafts/69.edit')

    def test_omits_domain_if_same_as_series(self):
        zerg = SeriesFactory.create(name='zerg')
        result = note_url(
            {'series': zerg},
            note=NoteFactory(series=zerg, pk=69),
            tag_filter=TagFilter.parse('foo+bar'),
            drafts=True)

        self.assertEqual(result, '/tagged/bar+foo/drafts/69')

    def test_omits_drafts_if_false(self):
        result = note_url(
            {},
            note=NoteFactory(series=SeriesFactory.create(name='zerg'), pk=69),
            tag_filter=TagFilter.parse('foo+bar'),
            drafts=False)

        self.assertEqual(result, 'https://zerg.example.org/tagged/bar+foo/69')

    def test_omits_tag_filter_if_false(self):
        result = note_url(
            {},
            note=NoteFactory(series=SeriesFactory.create(name='zerg'), pk=69),
            tag_filter=TagFilter(),
            drafts=False)

        self.assertEqual(result, 'https://zerg.example.org/69')

    def test_omits_tag_filter_if_omitted(self):
        result = note_url(
            {},
            note=NoteFactory(series=SeriesFactory.create(name='zerg'), pk=69),
            tag_filter=None,
            drafts=False)

        self.assertEqual(result, 'https://zerg.example.org/69')

    def test_root_if_same_series(self):
        zerg = SeriesFactory.create(name='zerg')
        result = note_url(
            {'series': zerg},
            note=NoteFactory(series=zerg, pk=69),
            tag_filter=None,
            drafts=False)

        self.assertEqual(result, '/69')

    def test_aquires_arguments_from_context(self):
        zerg = SeriesFactory.create(name='zerg')
        result = note_url(
            {
                'series': zerg,
                'note': NoteFactory(series=zerg, pk=69),
                'tag_filter': TagFilter.parse('-sad'),
                'drafts': True,
            },
        )

        self.assertEqual(result, '/tagged/-sad/drafts/69')

    def test_gives_priority_to_args(self):
        spof = SeriesFactory.create(name='spof')
        result = note_url(
            {
                'series': spof,
                'note': NoteFactory.create(series=spof),
                'tag_filter': TagFilter.parse('-sad'),
                'drafts': True,
            },
            note=NoteFactory(series=SeriesFactory.create(name='glog'), pk=69),
            tag_filter=TagFilter(),
            drafts=False,
        )

        self.assertEqual(result, 'https://glog.example.org/69')


@override_settings(NOTES_DOMAIN='example.org')
class TestProfileUrl(TestCase):

    def test_uses_slug_and_series(self):
        person = PersonFactory(slug='slug-of-person')
        series = SeriesFactory(name='name-of-series', editors=[person])

        result = profile_url({'series': series}, person)

        self.assertEqual(result, 'https://name-of-series.example.org/slug-of-person')

    def test_defaults_to_subject_of_page(self):
        person = PersonFactory(slug='slug-of-person')

        result = profile_url({'person': person})

        self.assertEqual(result, 'https://example.org/slug-of-person')
