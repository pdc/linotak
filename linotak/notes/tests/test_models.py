from django.db import transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from unittest.mock import patch, Mock

from ...matchers_for_mocks import DateTimeTimestampMatcher
from ...images.models import Image, wants_data
from ..models import Locator, LocatorImage, Tag, Note
from ..tag_filter import TagFilter
from .. import tasks
from .factories import NoteFactory, SeriesFactory, LocatorFactory


class TestFactories(TestCase):
    """Test Factories."""

    def test_note_has_author_who_is_editor_in_series(self):
        note = NoteFactory.create()

        self.assertTrue(note.author.native_name)
        self.assertTrue(note.series.editors.filter(pk=note.author.pk).exists())

    def test_note_with_series(self):
        series = SeriesFactory.create()
        note = NoteFactory.create(series=series)

        self.assertTrue(note.author.native_name)
        self.assertTrue(note.series.editors.filter(pk=note.author.pk).exists())


class TestSeriesIconRepresentations(TestCase):

    def test_without_icon_there_are_no_representations_duh(self):
        subject = SeriesFactory.create(icon=None)

        result = subject.icon_representations()

        self.assertFalse(result)

    def test_with_large_image_returns_longish_list(self):
        image = Image.objects.create(data_url='https://example.com/x.png')
        subject = SeriesFactory.create(icon=image)
        with patch.object(image, 'find_square_representation') as find_square_representation:
            find_square_representation.side_effect = lambda size: 'R(%s)' % size

            result = subject.icon_representations()

        self.assertEqual(set(result), {'R(%d)' % x for x in [16, 32, 48, 64, 192]})

    def test_also_does_apple_touch_icons(self):
        image = Image.objects.create(data_url='https://example.com/x.png')
        subject = SeriesFactory.create(apple_touch_icon=image)
        with patch.object(image, 'find_square_representation') as find_square_representation:
            find_square_representation.side_effect = lambda size: 'R(%s)' % size

            result = subject.apple_touch_icon_representations()

        self.assertEqual(set(result), {'R(%d)' % x for x in [120, 180, 152, 167]})

    def test_omits_unavailable_representations(self):
        image = Image.objects.create(data_url='https://example.com/x.png')
        subject = SeriesFactory.create(icon=image)
        with patch.object(image, 'find_square_representation') as find_square_representation:
            find_square_representation.side_effect = lambda size: 'R(%s)' % size if size < 48 else None

            result = subject.icon_representations()

        self.assertEqual(set(result), {'R(%d)' % x for x in [16, 32]})


class TestNoteTitle(TestCase):
    """Test generating titles from notes.

    Notes don’t have titles, so we grab the first N words of the text.
    """

    def test_short_note_is_its_own_title(self):
        result = Note(text='Hello, world').short_title()

        self.assertEqual(result, 'Hello, world')

    def test_shortens_long_single_paragraph(self):
        result = Note(text='This is a very long paragraph contrived to illustrate the shortening of note titles').short_title()

        self.assertEqual(result, 'This is a very long paragraph …')

    def test_takes_first_line_if_multiline(self):
        result = Note(text='Short title\nThis is a very long paragraph contrived to illustrate the shortening of note titles').short_title()

        self.assertEqual(result, 'Short title')

    def test_choosese_words_to_make_30_chars_or_so(self):
        result = Note(text='A web app for designing computer keyboard layouts!').short_title()

        self.assertEqual(result, 'A web app for designing computer …')

    def test_uses_short_title_for_dunder_dunder_str(self):
        result = str(Note(text='This is a very long paragraph contrived to illustrate the shortening of note titles'))

        self.assertEqual(result, 'This is a very long paragraph …')


class TestNoteExtractSubjects(TestCase):
    """Test Note.extract_subjects."""

    def test_converts_http_link(self):
        note = NoteFactory.create(text='http://example.com/1')

        result = note.extract_subject()

        self.assertTrue(result)
        self.assertFalse(note.text)  # No text remains
        self.assertEqual([x.url for x in note.subjects.all()], ['http://example.com/1'])

    def test_retains_balance_of_text(self):
        note = NoteFactory.create(text='Why hello! http://example.com/1')

        result = note.extract_subject()

        self.assertTrue(result)
        self.assertEqual(note.text, 'Why hello!')
        self.assertEqual([x.url for x in note.subjects.all()], ['http://example.com/1'])

    def test_strips_whitespace(self):
        note = NoteFactory.create(text='Why hello!\n\n http://example.com/1 \n\n')

        result = note.extract_subject()

        self.assertTrue(result)
        self.assertEqual(note.text, 'Why hello!')
        self.assertEqual([x.url for x in note.subjects.all()], ['http://example.com/1'])

    def test_ignores_urls_with_text_following(self):
        note = NoteFactory.create(text='http://example.com/1 Blort')

        result = note.extract_subject()

        self.assertFalse(result)
        self.assertEqual(note.text, 'http://example.com/1 Blort')
        self.assertEqual([x.url for x in note.subjects.all()], [])

    def test_matches_multiple_urls(self):
        note = NoteFactory.create(text='Many! http://example.com/1 https://example.com/2')

        result = note.extract_subject()

        self.assertTrue(result)
        self.assertEqual(note.text, 'Many!')
        self.assertEqual({x.url for x in note.subjects.all()}, {'http://example.com/1', 'https://example.com/2'})

    def test_matches_with_empty_path(self):
        note = NoteFactory.create(text='Yo! http://example.com/')

        result = note.extract_subject()

        self.assertTrue(result)
        self.assertEqual(note.text, 'Yo!')
        self.assertEqual([x.url for x in note.subjects.all()], ['http://example.com/'])

    def test_matches_URL_sans_path(self):
        note = NoteFactory.create(text='Yo! http://example.com')

        result = note.extract_subject()

        self.assertTrue(result)
        self.assertEqual(note.text, 'Yo!')
        self.assertEqual([x.url for x in note.subjects.all()], ['http://example.com/'])

    def test_matches_via_between_URLs(self):
        note = NoteFactory.create(text='https://example.com/1 via https://example.com/2')

        result = note.extract_subject()

        # Then we have 1 subject and it has a ‘via’ link.
        self.assertEqual([x.url for x in note.subjects.all()], ['https://example.com/1'])
        self.assertEqual(note.subjects.all()[0].via.url, 'https://example.com/2')

    def test_moves_subjects_to_via_if_so_instructed(self):
        # Given a note originally created with 2 URLs mentioned without a ‘via’ relationship:
        note = NoteFactory.create(subjects=[
            LocatorFactory.create(url='https://example.com/1'),
            LocatorFactory.create(url='https://example.com/2')
        ])

        # When editing to add ‘via’ between the URLs
        note.text = 'Hoo https://example.com/1 via https://example.com/2'
        note.save()
        note.extract_subject()

        # Then we have 1 subject and it has a "via" link.
        self.assertEqual([x.url for x in note.subjects.all()], ['https://example.com/1'])
        self.assertEqual(note.subjects.all()[0].via.url, 'https://example.com/2')

    def test_deletes_subjects_if_removed_from_text(self):
        # Given a note originally created with 2 URLs mentionedp:
        note = NoteFactory.create(subjects=[
            LocatorFactory.create(url='https://example.com/1'),
            LocatorFactory.create(url='https://example.com/2')
        ])

        # When editing to remove one URL:
        note.text = 'Lolwut https://example.com/2 https://example.com/3'
        note.save()
        note.extract_subject()

        # Then we have 1 URL
        self.assertEqual([x.url for x in note.subjects.all()], ['https://example.com/2', 'https://example.com/3'])
        self.assertFalse(note.subjects.all()[0].via)

    def test_returns_false_if_no_urls(self):
        note = NoteFactory.create(text='Banana frappé')

        result = note.extract_subject()

        self.assertFalse(result)
        self.assertEqual(note.text, 'Banana frappé')
        self.assertEqual([x.url for x in note.subjects.all()], [])

    def test_extracts_hashtags(self):
        note = NoteFactory.create(text='HelloWorld! #greeting https://example.com/1/ #camelCase')

        result = note.extract_subject()

        self.assertTrue(result)
        self.assertEqual(note.text, 'HelloWorld!')
        self.assertEqual([x.url for x in note.subjects.all()], ['https://example.com/1/'])
        self.assertEqual({x.name for x in note.tags.all()}, {'greeting', 'camelcase'})
        self.assertEqual({x.label for x in note.tags.all()}, {'greeting', 'camel case'})

    def test_extracts_hashtags_at_start(self):
        note = NoteFactory.create(text='#TokyoCameraClub #Japan #torii')

        result = note.extract_subject()

        self.assertTrue(result)
        self.assertEqual(note.text, '')
        self.assertEqual({x.name for x in note.tags.all()}, {'tokyocameraclub', 'japan', 'torii'})

    def test_deletes_unwanted_tags(self):
        note = NoteFactory.create(tags=['bimble', 'unwanted'], text='Lol #wimble #bimble')

        result = note.extract_subject()

        self.assertTrue(result)
        self.assertEqual(note.text, 'Lol')
        self.assertEqual({x.name for x in note.tags.all()}, {'wimble', 'bimble'})


class TestNoteTextWithLinks(TestCase):

    def test_adds_tags_with_hashes(self):
        note = NoteFactory.create(text='Hello, world', tags=['bamboo', 'firefly'], subjects=[
            LocatorFactory.create(url='https://example.com/1'), LocatorFactory.create(url='https://example.com/2'),
        ])

        self.assertEqual(
            note.text_with_links(),
            'Hello, world\n\n#bamboo #firefly\n\nhttps://example.com/1\nhttps://example.com/2')

    def test_makes_tags_camel_case(self):
        note = NoteFactory.create(text='Hello, world', tags=['bambooFirefly'])

        self.assertEqual(
            note.text_with_links(),
            'Hello, world\n\n#bambooFirefly')

    def test_adds_vias(self):
        note = NoteFactory.create(text='Hello, world', subjects=[
            LocatorFactory.create(
                url='https://example.com/1',
                via=LocatorFactory.create(
                    url='https://example.com/2',
                    via=LocatorFactory.create(url='https://example.com/3'))),
        ])

        self.assertEqual(
            note.text_with_links(),
            'Hello, world\n\nhttps://example.com/1\n via https://example.com/2\n via https://example.com/3')


class TestNoteAbsoluteUrl(TestCase):
    # These tests test the URL patterns so they will need amending if the URL patterns change!

    def test_works_without_extra_args(self):
        note = NoteFactory.create(published=timezone.now())

        self.assertEqual(note.get_absolute_url(), '/%d' % note.pk)

    def test_allows_replacing_view(self):
        note = NoteFactory.create()

        self.assertEqual(note.get_absolute_url(view='edit'), '/drafts/%d.edit' % note.pk)

    def test_can_add_tags(self):
        note = NoteFactory.create()

        self.assertEqual(note.get_absolute_url(tag_filter=TagFilter.parse('foo+bar')), '/tagged/bar+foo/drafts/%d' % note.pk)

    def test_can_make_include_host(self):
        note = NoteFactory.create(series__name='bomp', published=timezone.now())

        with self.settings(NOTES_DOMAIN='notes.example.org'):
            self.assertEqual(note.get_absolute_url(with_host=True), 'https://bomp.notes.example.org/%d' % note.pk)


class TestLocatorFetchPageUpdate(TransactionTestCase):
    """Test locator_fetch_page_update."""

    def test_queues_fetch_when_locator_created(self):
        """Test locator_fetch_page_update queues fetch when locator created."""
        with self.settings(NOTES_FETCH_LOCATORS=True), patch.object(tasks, 'fetch_locator_page') as fetch_locator_page:
            with transaction.atomic():
                locator = Locator.objects.create(url='https://example.com/1')

                self.assertFalse(fetch_locator_page.delay.called)
                # Not queued during the transaction to avoid race condition.

            fetch_locator_page.delay.assert_called_once_with(locator.pk, if_not_scanned_since=None)

    def test_doesnt_queue_if_settings_not_set(self):
        """Test locator_fetch_page_update doesnt queue if settings not set."""
        with self.settings(NOTES_FETCH_LOCATORS=False), patch.object(tasks, 'fetch_locator_page') as fetch_locator_page:
            Locator.objects.create(url='https://example.com/1')

            self.assertFalse(fetch_locator_page.delay.called)

    def test_doesnt_queue_if_not_newly_created(self):
        """Test locator_fetch_page_update doesnt queue if not newly created"""
        with self.settings(NOTES_FETCH_LOCATORS=True), patch.object(tasks, 'fetch_locator_page') as fetch_locator_page:
            locator = Locator.objects.create(url='https://example.com/1')
            locator.title = 'FOO'
            locator.save()

            fetch_locator_page.delay.assert_called_once_with(locator.pk, if_not_scanned_since=None)


class TestLocatorQueueFetch(TransactionTestCase):

    def test_passes_none_if_never_scanned(self):
        locator = Locator.objects.create(url='https://example.com/1')

        with patch.object(tasks, 'fetch_locator_page') as fetch_locator_page:
            locator.queue_fetch()

        fetch_locator_page.delay.assert_called_once_with(locator.pk, if_not_scanned_since=None)

    def test_value_that_can_return_original_datetime(self):
        locator = Locator.objects.create(url='https://example.com/1', scanned=timezone.now())

        with patch.object(tasks, 'fetch_locator_page') as fetch_locator_page:
            locator.queue_fetch()

        fetch_locator_page.delay.assert_called_once_with(locator.pk, if_not_scanned_since=DateTimeTimestampMatcher(locator.scanned))


class TestLocatorMainImage(TestCase):

    def test_returns_most_prominent_image(self):
        locator = Locator.objects.create(url='https://example.com/1')
        LocatorImage.objects.bulk_create([
            LocatorImage(locator=locator, image=Image.objects.create(data_url='https://example.com/1', width=500, height=300)),
            LocatorImage(locator=locator, image=Image.objects.create(data_url='https://example.com/2', width=500, height=400), prominence=3),
            LocatorImage(locator=locator, image=Image.objects.create(data_url='https://example.com/3', width=500, height=500)),
        ])

        result = locator.main_image()

        self.assertEqual(result.data_url, 'https://example.com/2')

    def test_returns_largest_image(self):
        locator = Locator.objects.create(url='https://example.com/1')
        LocatorImage.objects.bulk_create([
            LocatorImage(locator=locator, image=Image.objects.create(data_url='https://example.com/100', width=100, height=50)),
            LocatorImage(locator=locator, image=Image.objects.create(data_url='https://example.com/500', width=500, height=400)),
            LocatorImage(locator=locator, image=Image.objects.create(data_url='https://example.com/50', width=60, height=60)),
        ])

        result = locator.main_image()

        self.assertEqual(result.data_url, 'https://example.com/500')

    def test_queues_retrieval_of_unsized_images(self):
        locator = Locator.objects.create(url='https://example.com/1')
        image = Image.objects.create(data_url='https://example.com/500')
        LocatorImage.objects.bulk_create([
            LocatorImage(locator=locator, image=Image.objects.create(data_url='https://example.com/100', width=100, height=50)),
            LocatorImage(locator=locator, image=image),
            LocatorImage(locator=locator, image=Image.objects.create(data_url='https://example.com/50', width=60, height=60)),
        ])

        with patch.object(wants_data, 'send') as wants_data_send:
            result = locator.main_image()

        self.assertEqual(result.data_url, 'https://example.com/100')
        wants_data_send.assert_called_once_with(Image, instance=image)


class TestLocatorViaChain(TestCase):

    def test_returns_locators_in_via_order(self):
        mention2 = LocatorFactory.create(via=None)
        mention1 = LocatorFactory.create(via=mention2)
        original = LocatorFactory.create(via=mention1)

        result = original.via_chain()

        self.assertEqual(result, [mention1, mention2])


class TestTag(TestCase):

    def test_can_create_from_camel_case(self):
        result = Tag.objects.get_tag('fooBar')

        self.assertEqual(result.name, 'foobar')

    def test_creates_or_gets_existing(self):
        tag1 = Tag.objects.get_tag('fooBar')
        tag2 = Tag.objects.get_tag('FooBAR')

        self.assertEqual(tag1.pk, tag2.pk)

    def test_invents_label_if_none_supplied(self):
        tag = Tag.objects.get_tag('fooBar')

        self.assertEqual(tag.label, 'foo bar')

    def test_retains_capitalized_words(self):
        tag = Tag.objects.get_tag('fooBAR')

        self.assertEqual(tag.label, 'foo BAR')
