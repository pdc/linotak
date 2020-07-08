"""Scanner: look for interesting llinks and microformats2 properties in a web page.

Find (meta)data in a web page, an return it in the form of a
list of ’stuff’ (linkks, properties, and microforat2 structures like h-entrry
instances).
"""

import json
from html.parser import HTMLParser
import re
from urllib.parse import urljoin

from django.utils.dateparse import parse_date, parse_datetime


class StuffHolderMixin:
    """Mixin for objects that accumulate stuff and need to pick it apart to make bigger stuff."""

    stuff = []  # Must be overridden in subclass.

    def pop_stuff(self, cls, html_class):
        """Return best match amongst this tag’s stuff & remove it.

        Arguments --
            cls -- Python class of the type of stuff we want
            html_class -- microformats2 class to look for on the stuff
        """
        return _pop_stuff(self.stuff, cls, html_class)

    def pop_stuff_strictly(self, cls, html_class):
        """Return a match amongst this tag’s stuff & remove it.

        Arguments --
            cls -- Python class of the type of stuff we want
            html_class -- microformats2 class to look for on the stuff
        """
        return _pop_stuff_strictly(self.stuff, cls, html_class)


def _pop_stuff(stuff, cls, html_class):
    """Return best match amongst this stuff & remove it.

    Arguments --
        stuff -- list of objects collected from an element in a web page
        cls -- Python class of the type of stuff we want
        html_class -- microformats2 class to look for on the stuff
    """
    best = None
    best_is_classy = False
    for i, x in enumerate(stuff):
        if not isinstance(x, cls):
            continue
        classy = html_class in x.classes
        if best is None or classy and not best_is_classy:
            best, best_is_classy = i, classy
    if best is not None:
        return stuff.pop(best)


def _pop_stuff_strictly(stuff, cls, html_class):
    """Return a match amongst this stuff & remove it.

    Arguments --
        stuff -- list of objects collected from an element in a web page
        cls -- Python class of the type of stuff we want
        html_class -- microformats2 class to look for on the stuff
    """
    best = None
    for i, x in enumerate(stuff):
        if isinstance(x, cls) and html_class in x.classes:
            best = i
    if best is not None:
        return stuff.pop(best)


class Tag(StuffHolderMixin):
    """Somewhere to store information about a tag being processed."""

    def __init__(self, name, attrs):
        """Create instance with this element type and attributes.

        Arguments --
            name -- name of element, lowercase
            attrs -- list of (key, value) paris
        """
        self.name = name
        self.attrs = attrs
        self.classes = (self.get('class') or '').split()
        self.stuff = []

    def get(self, name):
        """Return value of this attribute, or None."""
        matches = [v for k, v in self.attrs if k == name]
        return matches[-1] if matches else None

    def __str__(self):
        return '<%s%s>' % (self.name, ''.join('.' + x for x in self.classes))


no_content_tags = {
    'br'
    'img',
    'link',
    'meta',
}


class StuffBase:
    """Base class for things in the stuff lists."""

    def __repr__(self):
        """Create representation that omits defaulted parameters."""
        xs = self.to_tuple()
        while xs and xs[-1] is None:
            xs = xs[:-1]
        if len(xs) == 1:
            return '%s(%r)' % (self.__class__.__name__, xs[0])
        return '%s%r' % (self.__class__.__name__, xs)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.to_tuple() == other.to_tuple()
        return False

    def __neq__(self, other):
        if isinstance(other, Link):
            return self.to_tuple() != other.to_tuple()
        return False


class Property(StuffBase):
    """A simple property in the microformats2 sense.

    Expected to be consumed to form part of an h-something.
    """

    def __init__(self, classes, value=None, original=None):
        self.classes = [classes] if isinstance(classes, str) else classes
        self.value = value
        self.original = original

    def __str__(self):
        return '%s=%r' % (self.classes[0] if len(self.classes == 1) else self.classes, self.value)

    def to_tuple(self):
        return self.classes, self.value, self.original


class Link(StuffBase):
    """Information gleaned about a link."""

    def __init__(self, rel, href, type=None, title=None, text=None, classes=None, author=None, published=None):
        """Create instance with this rel and href."""
        self.rel = {rel} if isinstance(rel, str) else set(rel) if rel else set()
        self.href = href
        self.type = type
        self.title = title
        self.text = text
        self.classes = classes or []
        self.author = author
        self.published = published

    def __str__(self):
        return '%s (%s)' % (self.href, ' '.join(self.rel))

    def to_tuple(self):
        return self.rel, self.href, self.type, self.title, self.text, self.classes or None, self.author, self.published


class Img(StuffBase):
    """Information about an image link."""

    def __init__(self, src, type=None, title=None, text=None, classes=None, width=None, height=None):
        """Create instance with this src."""
        self.src = src
        self.type = type
        self.title = title
        self.text = text
        self.classes = classes or []
        self.width = width and int(width)
        self.height = height and int(height)

    def __str__(self):
        if self.width:
            return '%s (%dx%d)' % (self.src, self.width, self.height)
        return self.src

    def to_tuple(self):
        return self.src, self.type, self.title, self.text, self.classes, self.width, self.height


class Title(StuffBase):
    """Title for the page."""

    weight = 1

    def __init__(self, text=None, weight=None):
        self.text = text or ''
        if weight is not None:
            self.weight = weight

    def __str__(self):
        return self.text

    def to_tuple(self):
        if self.weight == 1:
            return self.text,
        return self.text, self.weight


class HSomething(StuffHolderMixin, StuffBase):
    """An h-xxx entity for which we do not have a specifc recognizer for yet."""

    def __init__(self, html_class, classes, stuff):
        self.html_class = html_class
        self.classes = classes.split(' ') if isinstance(classes, str) else classes
        self.stuff = stuff

    def to_tuple(self):
        return self.html_class, self.classes, self.stuff

    def __str__(self):
        prop = self.peek_stuff(Property, 'p-name')
        return '%s (%s)' % (prop.value, self.html_class) if prop else self.html_class


class HCard(StuffBase):
    """An h-card entity, representing a person."""

    def __init__(self, name=None, url=None, photo=None, classes=None, short_name=None):
        self.name = name
        self.url = url
        self.photo = photo
        self.classes = classes or []
        self.short_name = short_name

    def __str__(self):
        return self.name

    def to_tuple(self):
        return self.name, self.url, self.photo, self.classes, self.short_name


# Links with these rel attributes in an entry are considered to be links about the entry, not mentioned in the entry.
RELS_FOR_ENTRY_LINKS = {'webmention'}


class HEntry(StuffBase):
    """An h-entry instance, representing a blog entry or similar."""

    def __init__(self, href=None, name=None, summary=None, author=None, classes=None, role=None, images=None, links=None):
        self.href = href
        self.name = name
        self.summary = summary
        self.author = author
        self.classes = classes or []
        self.role = role
        self.images = images or []
        self.links = links or []

    def __str__(self):
        return self.name

    def to_tuple(self):
        return self.href, self.name, self.summary, self.author, self.classes, self.role, self.images, self.links


# Recognizers will be called by the scanner when various HTML things are parsed.
# They emit stuff form end-tag handlers, which is aggregated by the caller.


class LinkRecognizer:
    """Spots links and anchors in page."""

    def __init__(self):
        self.links_wanting_text = []

    def handle_base_url(self, base_url):
        self.base_url = base_url

    def handle_start_base(self, tag):
        href = tag.get('href')
        if href:
            self.base_url = href

    def handle_start_link(self, tag):
        rel = tag.get('rel')
        href = tag.get('href')
        if rel and href is not None:
            tag.is_link = Link(
                rel.split(), urljoin(self.base_url, href),
                normalize_whitespace(tag.get('type')), normalize_whitespace(tag.get('title')))

    def handle_end_link(self, tag):
        link = getattr(tag, 'is_link', None)
        if link:
            return [link]

    def handle_start_a(self, tag):
        href = tag.get('href')
        rel = tag.get('rel') or ''
        if href is not None and not href.startswith('#'):
            link = Link(rel.split(), urljoin(self.base_url, href), tag.get('type'), tag.get('title'), classes=tag.classes)
            tag.is_a = link
            self.links_wanting_text.append(link)

    def handle_text(self, descendant_tag, text):
        for link in self.links_wanting_text:
            link.text = (link.text or '') + text

    def handle_end_a(self, tag):
        link = getattr(tag, 'is_a', None)
        if link:
            assert(self.links_wanting_text[-1] is link)
            self.links_wanting_text.pop(-1)
            link.text = normalize_whitespace(link.text)
            return [link]

    def handle_end_input(self, tag):
        if any(x.startswith('u-') for x in tag.classes):
            # Special case! Possibly a URL hidden on a form? Seen in the wild on Tantek Çelik's blog
            return [Link(None, urljoin(self.base_url, tag.get('value')), classes=tag.classes)]

    def handle_start_img(self, tag):
        src = tag.get('src')
        if src is not None:
            tag.is_img = Img(
                urljoin(self.base_url, src),
                tag.get('type'),
                tag.get('title'),
                classes=tag.classes,
                width=tag.get('width'),
                height=tag.get('height'))

    def handle_end_img(self, tag):
        img = getattr(tag, 'is_img', None)
        if img:
            return [img]


class TitleRecognizer:

    in_head = False

    def handle_start_head(self, tag):
        self.in_head = True

    def handle_end_head(self, tag):
        self.in_head = False

    def handle_start_title(self, tag):
        if self.in_head:
            tag.is_title = Title()

    def handle_text(self, tag, text):
        if hasattr(tag, 'is_title'):
            tag.is_title.text += text

    def handle_end_title(self, tag):
        title = getattr(tag, 'is_title', None)
        if title:
            return [title]


class PropertyRecognizer:
    """Attempt to spot p-xxx properties."""

    def __init__(self, *args, **kwargs):
        self.open_properties = []

    def handle_start(self, tag):
        prop_names = [x for x in tag.classes if x.startswith('p-') or x.startswith('dt-')]
        if prop_names:
            tag.is_property = (prop_names, '')
            self.open_properties.append(tag)

    def handle_text(self, tag, text):
        self.add_text(text)

    def add_text(self, text):
        if text:
            for x in self.open_properties:
                prop_names, value = x.is_property
                x.is_property = prop_names, value + text

    def handle_end(self, tag):
        if self.open_properties and self.open_properties[-1] == tag:
            self.open_properties.pop(-1)
            prop_names, value = tag.is_property
            value = normalize_whitespace(value)
            original = None
            if tag.name == 'abbr':
                long_value = normalize_whitespace(tag.get('title'))
                if long_value and long_value != value:
                    original = value
                    value = long_value
            stuff = []
            p_names = [x for x in prop_names if x.startswith('p-')]
            stuff.extend(Property(t, value, original) for t in p_names)
            dt_names = [x for x in prop_names if x.startswith('dt-')]
            if dt_names:
                if not original:
                    original = value
                attr = tag.get('datetime')
                if attr:
                    value = attr
                value = parse_datetime(value) or parse_date(value) or value
                stuff.extend(Property(t, value, original) for t in dt_names)
            return stuff


whitespace_re = re.compile(r'\s+', re.MULTILINE)


def normalize_whitespace(s):
    return s and whitespace_re.sub(' ', s.strip())


class BlockquoteRecognizer:
    """Capture blockquites with h-cite references."""

    def __init__(self, *args, **kwargs):
        self.blockquotes = []

    def handle_start_blockquote(self, tag):
        self.blockquotes.append(tag)
        tag.blockquote_text = ''

    def handle_text(self, tag, text):
        if self.blockquotes and self.blockquotes[-1] == tag:
            tag.blockquote_text += text

    def handle_end_blockquote(self, tag):
        if self.blockquotes and self.blockquotes[-1] == tag:
            self.blockquotes.pop(-1)
            link = tag.pop_stuff(Link, 'h-cite')
            if link:
                link.rel.add('linotak:blockquote')
                link.text = tag.blockquote_text.strip()
                return [link]


class OGRecognizer:
    """Capture OpenGraph (og:-prefixed) properties."""

    def __init__(self):
        self.props = {}

    def handle_base_url(self, base_url):
        self.base_url = base_url

    def handle_end_meta(self, tag):
        if (
            (name := tag.get('property')) and name.startswith('og:')
            or (name := tag.get('name')) and name.startswith('twitter')
        ):
            value = tag.get('content')
            if value:
                self.props[name] = value
                return [Property(name, value)]

    def handle_end_body(self, tag):
        image_src = (src := self.props.pop('og:image', None) or self.props.pop('twitter:image', None)) and urljoin(self.base_url, src)
        title = self.props.pop('og:title', None) or self.props.pop('twitter:title', None)
        desc = self.props.pop('og:description', None) or self.props.pop('twitter:description', None)
        url = self.props.pop('og:url', None) or self.props.pop('twitter:url', None)
        result = [Property(k, v) for k, v in self.props.items()]
        if title or desc or url:
            url = urljoin(self.base_url, url or '')
            result.append(HEntry(url, title, desc, images=image_src and [Img(image_src)]))
        elif image_src:
            result.append(Img(image_src))
        return result


class HSomethingRecognizer:
    def handle_stuff(self, tag, stuff):
        h_classes = [x for x in tag.classes if x.startswith('h-')]
        if h_classes:
            other_classes = [x for x in tag.classes if not x.startswith('h-')]
            return [self.make_something(tag, h, other_classes, stuff) for h in h_classes]

    def make_something(self, tag, h_class, classes, stuff):
        m = getattr(self, 'make_h_%s' % h_class[2:], None)
        if m:
            return m(tag, classes, stuff)
        return HSomething(h_class, classes, stuff)

    def make_h_entry(self, tag, classes, stuff):
        link = tag.pop_stuff_strictly(Link, 'u-url')
        name_prop = tag.pop_stuff_strictly(Property, 'p-name')
        summary_prop = tag.pop_stuff_strictly(Property, 'p-summary')
        author_card = tag.pop_stuff(HCard, 'p-author')
        author_prop = tag.pop_stuff_strictly(Property, 'p-author')
        author = author_card or (HCard(name=author_prop.value) if author_prop else None)
        href = link.href if link else None
        name = name_prop.value if name_prop else link.title if link else None
        summary = summary_prop.value if summary_prop else link.text if link else None
        role = tag.get('role')
        images = [x for x in stuff if isinstance(x, Img)]
        links = [x for x in stuff if isinstance(x, Link) and (x.rel & RELS_FOR_ENTRY_LINKS)]
        return HEntry(href, name, summary, author=author, classes=tag.classes, role=role, images=images, links=links)

    def make_h_card(self, tag, classes, stuff):
        link = _pop_stuff(stuff, Link, 'u-url')
        photo = _pop_stuff(stuff, Img, 'u-photo')
        name_prop = _pop_stuff_strictly(stuff, Property, 'p-name')
        author_prop = _pop_stuff_strictly(stuff, Property, 'p-author')
        prop = name_prop or author_prop
        short_name = None
        if prop:
            if prop.original and prop.original != prop.value:
                # This happens if the outer element is an abbr giving a longer version of th name.
                short_name = normalize_whitespace(prop.original)
            name = prop.value
        elif link:
            name = link.text or link.title
        else:
            name = None
        if name:
            name = normalize_whitespace(name)
        return HCard(name, link, photo, short_name=short_name, classes=classes)

    hcite_props = {'u-url', 'p-name', 'p-summary', 'p-author', 'h-card'}

    def make_h_cite(self, tag, classes, stuff):
        link = _pop_stuff_strictly(stuff, Link, 'h-cite') or _pop_stuff(stuff, Link, 'u-url')
        if 'h-cite' not in link.classes:
            link.classes.append('h-cite')
        card = _pop_stuff(stuff, HCard, 'p-author')
        prop = _pop_stuff_strictly(stuff, Property, 'p-author')
        if card:
            link.author = card
        elif prop:
            link.author = HCard(prop.value)
        prop = _pop_stuff_strictly(stuff, Property, 'p-name')
        if prop:
            link.title = prop.value
        elif link.text:
            link.title = link.text
        if link.text == link.title:
            link.text = None
        prop = _pop_stuff_strictly(stuff, Property, 'dt-published')
        if prop:
            link.published = prop.value
        link.classes = [x for x in link.classes if x not in self.hcite_props]
        return link


class MastodonMediaGalleryRecognizer:
    """Recognize media gallery as seen on Mastodon entries."""

    def handle_end(self, tag):
        if tag.get('data-component') == 'MediaGallery':
            props = json.loads(tag.get('data-props'))
            stuff = []
            for x in props['media']:
                if x['type'] == 'image':
                    width = x['meta']['original']['width']
                    height = x['meta']['original']['height']
                    stuff.append(Img(x['url'], width=width, height=height))
            return stuff


class TwitterRecognizer:

    URL_PATTERN = re.compile(r'^https://twitter.com/(?P<user>\w+)/status/\d+')

    def handle_base_url(self, base_url):
        self.base_url = base_url

    def handle_end_body(self, tag):
        if m := self.URL_PATTERN.search(self.base_url):
            # Return title with lowest weight so it will give way to any better guess:
            return [Title(f"@{m['user']} on Twitter", weight=0)]


class PageScanner(HTMLParser):
    """Scan HTML and call methods in subclass as elements are detected."""

    default_recognizers = [
        PropertyRecognizer,
        LinkRecognizer,
        HSomethingRecognizer,
        TitleRecognizer,
        BlockquoteRecognizer,
        MastodonMediaGalleryRecognizer,
        OGRecognizer,
        TwitterRecognizer,
    ]

    def __init__(self, base_url, recognizers=None, *args, **kwargs):
        """Initialize this instance."""
        super().__init__(*args, **kwargs)
        self.recognizers = [(x() if callable(x) else x) for x in (recognizers or PageScanner.default_recognizers)]
        self.base_url = base_url
        if base_url:
            self.notify('handle_base_url', base_url)

        self.stack = []
        self.stuff = []

    def notify(self, meth_name, *args, **kwargs):
        """Notify recognizers of an HTML event."""
        for _ in self.iter_notify(meth_name, *args, **kwargs):
            pass

    def iter_notify(self, meth_name, *args, **kwargs):
        """Notify recognizers of an HTML event and yield their return values"""
        for recognizer in self.recognizers:
            meth = getattr(recognizer, meth_name, None)
            if meth:
                yield meth(*args, **kwargs)

    def handle_starttag(self, name, attrs):
        tag = Tag(name, attrs)
        self.notify('handle_start', tag)
        self.notify('handle_start_%s' % name.replace('-', '_'), tag)
        for k, v in attrs:
            self.notify('handle_attr_%s' % k.replace('-', '_'), tag, k, v)
        classes = tag.get('class')
        if classes:
            for c in classes.strip().split():
                self.notify('handle_class_%s' % c.replace('-', '_'), tag)

        # Treat ALT tag as text (as if images switched off).
        alt = tag.get('alt')
        if alt:
            self.notify('handle_text', tag, alt)

        self.stack.append(tag)
        if name in no_content_tags:
            self._pop_tag()

    def handle_endtag(self, name):
        """Pop tags from the stack until we have popped this one."""
        while self.stack:
            tag = self._pop_tag()
            if tag.name == name:
                break

    def _pop_tag(self):
        tag = self.stack.pop(-1)
        stuffs = [tag.stuff] if tag.stuff else []
        stuffs.extend(self.iter_notify('handle_end', tag))
        stuffs.extend(self.iter_notify('handle_end_%s' % tag.name.replace('-', '_'), tag))

        # Postprocess the collection of stuff to assemble larger structures.
        stuff = [x for xs in stuffs if xs for x in xs]
        for recognizer in self.recognizers:
            meth = getattr(recognizer, 'handle_stuff', None)
            if meth:
                result = meth(tag, stuff)
                if result is not None:
                    stuff = result

        # Bubble resulting stuff up to enclosing tag, or to scanner instance.
        recipent = (self.stack[-1] if self.stack else self)
        recipent.stuff.extend(stuff)
        return tag

    def handle_data(self, data):
        if self.stack:
            self.notify('handle_text', self.stack[-1], data)

    def close(self):
        """Additional call at end of file."""
        while self.stack:
            tag = self._pop_tag()
        super().close()
