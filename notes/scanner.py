from html.parser import HTMLParser
from urllib.parse import urljoin


class Tag:
    """A scratchpad used by the scanner for intermediate values whie scannign an element."""

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

    def pop_stuff(self, cls, html_class):
        """Return best match amongst this tag’s stuff & remove it.

        Arguments --
            cls -- Python class of the type of stuff we want
            html_class -- microformats2 class to look for on the stuff
        """
        best = None
        for i, x in enumerate(self.stuff):
            if isinstance(x, cls) and (best is None or html_class in x.classes):
                best = i
        if best is not None:
            return self.stuff.pop(best)


no_content_tags = {
    'br'
    'img',
    'link',
}


class PageParserBase(HTMLParser):
    """Scan HTML and call methods in subclass as elements are detected."""

    def __init__(self, base_url, *args, **kwargs):
        """Initialize this instance."""
        super().__init__(*args, **kwargs)
        self.base_url = base_url
        self.stack = []
        self.stuff = []

    def handle_starttag(self, name, attrs):
        super().handle_starttag(name, attrs)
        tag = Tag(name, attrs)
        self.handle_start(tag)
        m = getattr(self, 'handle_start_%s' % name.replace('-', '_'), None)
        if m:
            m(tag)
        for k, v in attrs:
            m = getattr(self, 'handle_attr_%s' % k.replace('-', '_'), None)
            if m:
                m(tag, k, v)
        self.stack.append(tag)
        if name in no_content_tags:
            self._pop_tag()

    def handle_endtag(self, name):
        super().handle_endtag(name)
        while self.stack:
            tag = self._pop_tag()
            if tag.name == name:
                break

    def _pop_tag(self):
        tag = self.stack.pop(-1)
        stuffs = [tag.stuff] if tag.stuff else []
        stuffs.append(self.handle_end(tag))

        m = getattr(self, 'handle_end_%s' % tag.name.replace('-', '_'), None)
        if m:
            stuffs.append(m(tag))
        recipent = (self.stack[-1] if self.stack else self)
        for stuff in stuffs:
            if stuff:
                recipent.stuff.extend(stuff)
        return tag

    def handle_data(self, data):
        super().handle_data(data)
        if self.stack:
            self.handle_text(self.stack[-1], data)

    def handle_start(self, tag):
        pass

    def handle_end(self, tag):
        """Handle end tag by returning list of stuff discovered in this tag."""
        return []

    def handle_text(self, tag, text):
        pass

    def handle_attr_class(self, tag, _, value):
        """Split classes and call related methods if they exist."""
        classes = value.split()
        for c in classes:
            m = getattr(self, 'handle_class_%s' % c.replace('-', '_'), None)
            if m:
                m(tag)

    def close(self):
        """Additional call at end of file."""
        while self.stack:
            tag = self._pop_tag()
        super().close()


class StuffBase:
    """Base class for things in the stuff lists."""

    def __repr__(self):
        xs = self.to_tuple()
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

    Expected to form part of an h-something.
    """

    def __init__(self, classes, value=None):
        self.classes = [classes] if isinstance(classes, str) else classes
        self.value = value

    def __str__(self):
        return '%s=%r' % (self.classes[0] if len(self.classes == 1) else self.classes, self.value)

    def to_tuple(self):
        return self.classes, self.value


class Link(StuffBase):
    """Information gleaned about a link."""

    def __init__(self, rel, href, type=None, title=None, text=None, classes=None, author=None):
        """Create instance with this rel and href."""
        self.rel = {rel} if isinstance(rel, str) else set(rel) if rel else set()
        self.href = href
        self.type = type
        self.title = title
        self.text = text
        self.classes = classes or []
        self.author = author

    def __str__(self):
        return '%s (%s)' % (self.href, ' '.join(self.rel))

    def to_tuple(self):
        return self.rel, self.href, self.type, self.title, self.text, self.classes, self.author


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


class LinkMixin:
    """Spots links and anchors in page."""

    def handle_start_link(self, tag):
        rel = tag.get('rel')
        href = tag.get('href')
        if rel and href is not None:
            tag.is_link = Link(rel, urljoin(self.base_url, href), tag.get('type'), tag.get('title'))

    def handle_end_link(self, tag):
        link = getattr(tag, 'is_link', None)
        if link:
            return [link]

    def handle_start_a(self, tag):
        href = tag.get('href')
        if href is not None and not href.startswith('#'):
            tag.is_a = Link(tag.get('rel') or [], urljoin(self.base_url, href), tag.get('type'), tag.get('title'), classes=tag.classes)

    def handle_text(self, tag, text):
        super().handle_text(tag, text)
        if hasattr(tag, 'is_a'):
            tag.is_a.text = (tag.is_a.text or '') + text

    def handle_end_a(self, tag):
        link = getattr(tag, 'is_a', None)
        if link:
            return [link]

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


class Title(StuffBase):
    """Title for the page."""

    def __init__(self, text=None):
        self.text = text or ''

    def __str__(self):
        return self.text

    def to_tuple(self):
        return self.text,


class TitleMixin:
    def handle_start_title(self, tag):
        tag.is_title = Title()

    def handle_text(self, tag, text):
        super().handle_text(tag, text)
        if hasattr(tag, 'is_title'):
            tag.is_title.text += text

    def handle_end_title(self, tag):
        return [getattr(tag, 'is_title', None)]


class PropertyMixin:
    """Attempt to spot p-xxx properties."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.open_properties = []

    def handle_start(self, tag):
        p_tags = [x for x in tag.classes if x.startswith('p-')]
        if p_tags:
            tag.is_property = [Property(x) for x in p_tags]
            self.open_properties.append(tag)

    def handle_text(self, tag, text):
        super().handle_text(tag, text)
        for x in self.open_properties:
            for p in x.is_property:
                p.value = (p.value or '') + text

    def handle_end(self, tag):
        stuff = super().handle_end(tag)
        if self.open_properties and self.open_properties[-1] == tag:
            self.open_properties.pop(-1)
            stuff.extend(tag.is_property)
        return stuff


class HCard(StuffBase):
    """An h-card instance, representing a person."""

    def __init__(self, name=None, url=None, photo=None):
        self.name = name
        self.url = url
        self.photo = photo

    def __str__(self):
        return self.name

    def to_tuple(self):
        return self.name, self.url, self.photo


class HCardMixin:

    def handle_class_h_card(self, tag):
        tag.is_hcard = HCard()

    def handle_end(self, tag):
        stuff = super().handle_end(tag) or []
        if hasattr(tag, 'is_hcard'):
            # Try to default the fields we dont have yet.
            card = tag.is_hcard
            if not card.photo:
                card.photo = tag.pop_stuff(Img, 'u-photo')
            if not card.url:
                card.url = tag.pop_stuff(Link, 'u-url')
            if not card.name:
                prop = tag.pop_stuff(Property, 'p-name')
                if prop:
                    card.name = prop.value
            if not card.name and card.url:
                card.name = card.url.text or card.url.title
            stuff.append(card)
        return stuff


class HCiteMixin:
    """Capture blockquites with h-cite references."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, *kwargs)
        self.blockquotes = []

    def handle_start_blockquote(self, tag):
        self.blockquotes.append(tag)
        tag.blockquote_text = ''

    def handle_text(self, tag, text):
        super().handle_text(tag, text)
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

    def handle_class_h_cite(self, tag):
        """Record that this an h-cite."""
        tag.is_cite = True

    def handle_end(self, tag):
        super().handle_end(tag)
        if hasattr(tag, 'is_cite'):
            link = tag.pop_stuff(Link, 'h-cite')
            if 'h-cite' not in link.classes:
                link.classes.append('h-cite')
            prop = tag.pop_stuff(Property, 'p-author')
            if prop:
                link.author = HCard(prop.value)
            return [link]


class PageScanner(PropertyMixin, HCardMixin, HCiteMixin, TitleMixin, LinkMixin, PageParserBase):
    """Scan page for links and stuff."""

    pass

