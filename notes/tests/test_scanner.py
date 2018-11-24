import datetime

from django.test import TestCase

from ..scanner import PageScanner, Title, Link, Img, Property, HCard, HEntry, HSomething


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

    def test_respects_base_tag(self):
        stuff = self.scan("""
            <html>
                <head><base href="http://example.com/foo/"></head>
                <body><a href="bar" class="u-syndication">Booble wooble</a></body>
            """)

        self.assertEqual(stuff, [
            Link(None, 'http://example.com/foo/bar', text='Booble wooble', classes=['u-syndication'])
        ])

    def test_makes_link_from_u_url_property(self):
        stuff = self.scan("""
            <input class="u-url url u-uid uid bookmark" type="url" size="70" style="max-width:100%"
                value="http://tantek.com/2013/073/b1/silos-vs-open-social-web" />
        """)

        self.assertEqual(stuff, [
            Link(None, 'http://tantek.com/2013/073/b1/silos-vs-open-social-web', classes=['u-url', 'url', 'u-uid', 'uid', 'bookmark'])
        ])


class TestPropertyCapture(ScanMixin, TestCase):
    def test_simple_plaintext_property(self):
        stuff = self.scan('<span class="p-name">Property Value</span>')
        self.assertEqual(stuff, [Property('p-name', 'Property Value')])

    def test_simple_datetime_property(self):
        stuff = self.scan('<time class="dt-published">2018-10-24</time>')
        self.assertEqual(stuff, [Property('dt-published', datetime.date(2018, 10, 24), original='2018-10-24')])

    def test_uses_datetime_attr_if_provided(self):
        stuff = self.scan('<time class="dt-start" datetime="2013-06-22">June 22</time>')
        self.assertEqual(stuff, [Property('dt-start', datetime.date(2013, 6, 22), 'June 22')])

    def test_simple_abbr_property(self):
        stuff = self.scan('<abbr class="p-name" title="Longer Value">Short Value</abbr>')
        self.assertEqual(stuff, [Property('p-name', 'Longer Value', original='Short Value')])

    def test_uses_alt_attr_of_img(self):
        stuff = self.scan('<img src="/img/1.jpeg" alt="Alice de Winter" class="p-name">')
        self.assertEqual(stuff, [Property('p-name', 'Alice de Winter'), Img('https://example.com/img/1.jpeg', classes=['p-name'])])


class TestHSomethingCapture(ScanMixin, TestCase):
    """Test HSomething capture."""

    def test_encapsulates_properties_and_links(self):
        stuff = self.scan("""
            <li class="h-event">
                In person, at <a class="p-name u-url" href="http://indiewebcamp.com/2013">IndieWebCamp 2013</a>,
                <time class="dt-start" datetime="2013-06-22">June 22</time>-<time class="dt-end" datetime="2013-06-23">23</time>
                in <span class="p-location h-adr"><span class="p-locality">Portland</span>, <span class="p-region">Oregon</span></span>
            </li>
        """)

        self.assertEqual(stuff, [
            HSomething('h-event', [], [
                Property('p-name', 'IndieWebCamp 2013'),
                Link(None, 'http://indiewebcamp.com/2013', text='IndieWebCamp 2013', classes=['p-name', 'u-url']),
                Property('dt-start', datetime.date(2013, 6, 22), original='June 22'),
                Property('dt-end', datetime.date(2013, 6, 23), original='23'),
                HSomething('h-adr', ['p-location'], [
                    Property('p-locality', 'Portland'),
                    Property('p-region', 'Oregon'),
                    Property('p-location', 'Portland, Oregon'),
                ])
            ])
        ])


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
                photo=Img('https://jeena.net/avatar.jpg', classes=['u-photo']),
            )
        ])

    def test_understands_explcit_p_name_field(self):
        stuff = self.scan("""
            <span class="h-card">
                <span class="p-name">Jet Mac Das</span>
            </span>
        """)

        self.assertEqual(stuff, [HCard(name='Jet Mac Das')])

    def test_unabbreviates_abbrev(self):
        stuff = self.scan('<abbr class="p-author h-card" title="Tantek Çelik">Çelik</abbr>')

        self.assertIn(HCard('Tantek Çelik', short_name='Çelik', classes=['p-author']), stuff)

    def test_understands_tantek_çelic(self):
        stuff = self.scan("""
            <a href="../" class="p-author h-card author-icon" rel="author" title="Tantek Çelik">
                <img src="../logo.jpg" alt="Tantek Çelik" />
            </a>
        """)

        self.assertEqual(stuff, [
             HCard(
                'Tantek Çelik',
                Link({'author'}, 'https://example.com/', title='Tantek Çelik', text='Tantek Çelik', classes=['p-author', 'h-card', 'author-icon']),
                Img('https://example.com/logo.jpg'), ['p-author', 'author-icon']),
        ])


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
                title='Rony Ngala',
                text="”… an @ mention that works across websites; so that you don't feel immovable from Twitter or Fb.”",
                classes=['external', 'text', 'h-cite'],
                author=HCard('Rony Ngala'))
            ])

    def test_citation_with_date_and_archived_version(self):
        stuff = self.scan("""
            <span class="h-cite">
                <span class="dt-published">2018-05-09</span>
                <span class="p-author">
                    <span class="h-card" style="white-space:nowrap">
                        <img src="https://seblog.nl/photo.jpg" class="u-photo" style="height:1.1em;vertical-align:-.1em" alt="" />
                        <a href="/User:Seblog.nl" title="User:Seblog.nl">Sebastiaan Andeweg</a>
                    </span>
                </span>:
                <cite>
                    <a class="external u-url p-name" href="https://seblog.nl/2018/05/09/5/de-magie-van-webmentions">De magie van Webmentions</a>
                </cite>
                (<a href="https://web.archive.org/web/20180509210136/https://seblog.nl/2018/05/09/5/de-magie-van-webmentions" class="external u-url">archived</a>)
            </span>
        """)

        self.assertIn(
            Link(
                None, 'https://seblog.nl/2018/05/09/5/de-magie-van-webmentions',
                title='De magie van Webmentions',
                classes=['external', 'h-cite'],
                author=HCard(
                    'Sebastiaan Andeweg',
                    Link(None, 'https://example.com/User:Seblog.nl', title='User:Seblog.nl', text='Sebastiaan Andeweg'),
                    Img('https://seblog.nl/photo.jpg', classes=['u-photo'])),
                published=datetime.date(2018, 5, 9)
            ), stuff)

    def test_citation_from_tantek_çelik(self):
        stuff = self.scan("""
            <cite class="h-cite"><a class="u-url p-name" href="http://tantek.com/2013/073/b1/silos-vs-open-social-web">On Silos vs an Open Social Web [#indieweb]</a> (<abbr class="p-author h-card" title="Tantek Çelik">Çelik</abbr> <time class="dt-published">2013-03-14</time>)</cite>)
        """)

        self.assertIn(
            Link(
                None, 'http://tantek.com/2013/073/b1/silos-vs-open-social-web',
                title='On Silos vs an Open Social Web [#indieweb]',
                classes=['h-cite'],
                published=datetime.date(2013, 3, 14),
                author=HCard('Tantek Çelik', short_name='Çelik', classes=['p-author'])
            ), stuff)


class TestHEntryMixin(ScanMixin, TestCase):
    """Want to recognize pages that ARE entries and pages containing entries."""

    def test_encloses_author_in_link(self):
        stuff = self.scan("""
            <div id="content" class="mw-body h-entry" role="main">
                    <a id="top"></a>
                    <a href="" class="u-url"></a>
                    <h1 id="firstHeading" class="firstHeading p-name" lang="en">Webmention</h1>
                    <p><span class="p-summary">
                        <b><dfn><a class="external text" href="https://webmention.net/draft/">Webmention</a></dfn></b>
                        is a web standard for mentions and conversations across the web, a powerful building block that is
                        used for a growing <a href="/federated" class="mw-redirect" title="federated">federated</a>
                        network of <a href="/comment" title="comment">comments</a>,
                        <a href="/like" title="like">likes</a>, <a href="/repost" title="repost">reposts</a>,
                        and other rich interactions across the decentralized social web.
                    </span></p>
        """)

        self.assertIn(
            HEntry(
                'https://example.com/1',
                'Webmention',
                'Webmention'
                    ' is a web standard for mentions and conversations across the web, a powerful building block that is'
                    ' used for a growing federated'
                    ' network of comments,'
                    ' likes, reposts,'
                    ' and other rich interactions across the decentralized social web.',
                classes=['mw-body', 'h-entry'],
                role='main'
            ),
            stuff)
