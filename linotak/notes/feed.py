"""Views fro notes."""

from django.conf import settings
from django.http import HttpResponse
from django.views.generic.list import BaseListView
from django.urls import reverse
import io

from ..xml_writer import Document
from .views import TaggedMixin, NotesMixin


class NoteFeedView(TaggedMixin, NotesMixin, BaseListView):
    """Generate XML feed in Atom format."""

    paginate_by = 30
    paginate_orphans = 3

    def paginate(self):
        """Query for stuff and return things."""
        queryset = self.get_queryset()
        page_size = self.get_paginate_by(queryset)
        return self.paginate_queryset(queryset, page_size)

    def get(self, request, *args, **kwargs):
        """Zum zub."""
        paginator, page, object_list, is_paginated =  self.paginate()

        doc = Document('feed', {'xml:lang': 'en-GB'}, prefix_namespaces={
            '': 'http://www.w3.org/2005/Atom',
            'fh': 'http://purl.org/syndication/history/1.0',
        })
        doc.add_child('id', {}, self.get_feed_id())
        doc.add_child('title', {}, self.series.title)
        doc.add_child('link', {'href': self.get_feed_url('feed'), 'rel': 'self'})
        doc.add_child('link', {'href': self.get_feed_url('list')})
        updated = max(self.get_entry_updated(e) for e in object_list)
        doc.add_child('updated', {}, atom_datetime(updated))

        for note in object_list:
            e = doc.add_child('entry')
            e.add_child('id', {}, self.get_entry_id(note))
            e.add_child('title', {}, self.get_entry_title(note))
            author = self.get_entry_author(note)
            if author:
                ee = e.add_child('author')
                for k, v in author.items():
                    ee.add_child(k, {}, v)
            e.add_child('content', {}, self.get_entry_content(note))
            e.add_child('published', {}, atom_datetime(self.get_entry_published(note)))
            e.add_child('updated', {}, atom_datetime(self.get_entry_updated(note)))
            e.add_child('link', {'href': self.get_entry_link(note)})

        buf = io.BytesIO()
        doc.write_to(buf)
        return HttpResponse(buf.getvalue(), content_type='application/atom+xml; charset=UTF-8')

    def get_feed_id(self):
        """Return an absolute IRI (~URL) that is the permanet ID of this feed."""
        return self.get_feed_url('list')

    def get_feed_url(self, view):
        tag_filter = self.tag_filter
        path = reverse('notes:%s' % view, kwargs={
            'tags': tag_filter.unparse() if tag_filter else '',
            'drafts': False,
            'page': 1,
        })
        return 'https://%s.%s%s' % (self.series.name, settings.NOTES_DOMAIN, path)

    def get_entry_id(self, entry):
        """Return an absolute URL that is permanent ID for this entry."""
        return self.get_entry_link(entry, with_tags=False)

    def get_entry_title(self, entry):
        """Return title of note."""
        return str(entry.pk)  # We use the note number as the title for now.

    def get_entry_content(self, entry):
        """Return content of note."""
        return entry.text_with_links()

    def get_entry_author(self, entry):
        """Return author of entry, or None.

        Author is object with at least name field.
        May have uri, email.
        """
        return {'name': entry.author.native_name}

    def get_entry_published(self, entry):
        """Return latest update date + time of the entry."""
        return entry.published

    def get_entry_updated(self, entry):
        """Return latest update date + time of the entry."""
        return entry.published

    def get_entry_link(self, entry, with_tags=True):
        """Link to the page for this entry."""
        tag_filter = self.tag_filter
        path = reverse('notes:detail', kwargs={
            'tags': self.tag_filter.unparse() if with_tags and tag_filter else '',
            'drafts': False,
            'pk': entry.pk,
        })
        return 'https://%s.%s%s' % (self.series.name, settings.NOTES_DOMAIN, path)


def atom_datetime(d):
    """Reuturn this dattime formtted for Atom."""
    return d.isoformat().replace('+00:00', 'Z')
