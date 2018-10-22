from django.test import TestCase

from ..scanner import PageScanner, Title, Link, Img, HCard


class ScanMixin:
    """Mixin to add a shorthand for scanning an HTML fragment."""

    maxDiff = None

    def scan(self, text):
        scanner = PageScanner('https://example.com/1')
        scanner.feed(text)
        scanner.close()
        return scanner.stuff


class TestLinksMixin(ScanMixin, TestCase):
    """Test PageScanner."""

    def test_does_nothing_if_no_input(self):
        stuff = self.scan('')

        self.assertFalse(stuff)

    def test_grabs_links(self):
        stuff = self.scan("""
            <head>
                <link rel=webmention href="https://webmention.io/indiewebcamp/webmention">
                <link rel="stylesheet" href="https://media.example.com/style.css" type="text/css"/>
                <link rel="next" title="More"  href=https://example.com/2>
        """)

        self.assertEqual(stuff, [
            Link('webmention', 'https://webmention.io/indiewebcamp/webmention'),
            Link('stylesheet', 'https://media.example.com/style.css', 'text/css'),
            Link('next', 'https://example.com/2', title='More'),
        ])

    def test_resolves_relative_to_document(self):
        stuff = self.scan("""
            <link rel="next" href="2"/>
        """)

        self.assertEqual(stuff, [
            Link('next', 'https://example.com/2'),
        ])

    def test_spots_a_tags_as_well(self):
        stuff = self.scan("""
            <a href="https://webmention.net/draft/">Webmention</a>
        """)

        self.assertEqual(stuff, [
            Link(set(), 'https://webmention.net/draft/', text='Webmention')])

    def test_records_classes_as_well(self):
        stuff = self.scan("""
            <a class="external text" href="https://webmention.net/draft/">Webmention</a>
        """)

        self.assertEqual(stuff, [
            Link({}, 'https://webmention.net/draft/', text='Webmention', classes=['external', 'text'])])

    def test_ignores_internal_anchor(self):
        stuff = self.scan("""
                <a id="top"></a>
        """)

        self.assertFalse(stuff)

    def test_handles_self_link(self):
        stuff = self.scan("""
                <a href="" class="u-url"></a>
        """)

        self.assertEqual(stuff, [
            Link([], 'https://example.com/1', classes=['u-url'])
        ])

    def test_ignores_internal_link(self):
        stuff = self.scan("""
                <a href="#mw-head">navigation</a>
        """)

        self.assertFalse(stuff)

    def test_title(self):
        stuff = self.scan("""
            <html>
                <head>
                    <title>This is the title</title>
        """)

        self.assertEqual(stuff, [Title('This is the title')])

    def test_a_with_text(self):
        stuff = self.scan("""
            <a href="/User:Jeena.net"
                title="User:Jeena.net">Jeena Paradies</a>
        """)

        self.assertEqual(stuff, [
            Link(None, 'https://example.com/User:Jeena.net', title='User:Jeena.net', text='Jeena Paradies'),
        ])

    def test_img(self):
        stuff = self.scan("""
            <img src="https://jeena.net/avatar.jpg" class="u-photo"
                style="height:1.1em;vertical-align:-.1em" alt="" />
        """)

        self.assertEqual(stuff, [Img('https://jeena.net/avatar.jpg', classes=['u-photo'])])


class TestHCardMixin(ScanMixin, TestCase):

    def test_spots_person(self):
        stuff = self.scan("""
            <h4><span class="mw-headline" id="Jeena_with_jeena.net">Jeena with jeena.net</span></h4>
            <ul><li> <span class="h-card"><img src="https://jeena.net/avatar.jpg" class="u-photo"
                style="height:1.1em;vertical-align:-.1em" alt="" /> <a href="/User:Jeena.net"
                title="User:Jeena.net">Jeena Paradies</a></span>
        """)

        self.assertEqual(stuff, [
            HCard(
                name='Jeena Paradies',
                url=Link(None, 'https://example.com/User:Jeena.net', title='User:Jeena.net', text='Jeena Paradies'),
                photo=Img('https://jeena.net/avatar.jpg', classes=['u-photo'])
            )
        ])

    def test_understands_explcit_p_name_field(self):
        stuff = self.scan("""
            <span class="h-card">
                <span class="p-name">Jet Mac Das</span>
            </span>
        """)

        self.assertEqual(stuff, [HCard(name='Jet Mac Das')])


class TestHCiteMixin(ScanMixin, TestCase):

    def test_encloses_author_in_link(self):
        stuff = self.scan("""
            <blockquote>
                ”… an @ mention that works across websites; so that you don't feel immovable from Twitter or Fb.”
                <cite class="h-cite">— <a class="external text" href="https://twitter.com/rngala/status/852354426983591937"><span class="p-author">Rony Ngala</span></a></cite>
            </blockquote>
        """)

        self.assertEqual(stuff, [
            Link(
                'linotak:blockquote',
                'https://twitter.com/rngala/status/852354426983591937',
                text="”… an @ mention that works across websites; so that you don't feel immovable from Twitter or Fb.”",
                classes=['external', 'text', 'h-cite'],
                author=HCard('Rony Ngala'))
            ])
