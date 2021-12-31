"""XML Blob writer.

This is designed to make documents that are as readable as possible:
namespace definitions are all moved to the outermost element,
and use consistent prefixes. Needless definitions are omitted.
"""

from xml.sax.saxutils import XMLGenerator


def expand_qname(qname, prefix_namespaces):
    """Given a qname, return (NAMESPACE_URL, LOCAL_NAME).

    Arguments --
        qname -- an XML qualified name, e.g., `feed` or `atom:feed`
        prefix_namepsaces -- map from prefix like `atom` to URL of namespace

    If there is an entry in prefix_namespaces for the empty string
    then this is the namespace used for unprefixed names.
    """
    prefix, lname = split_qname(qname)
    if prefix:
        return prefix_namespaces[prefix], lname
    if "" in prefix_namespaces:
        return prefix_namespaces[""], lname
    return None, qname


def split_qname(qname):
    """Given a qname, return prefix and lname."""
    parts = qname.split(":", 1)
    if len(parts) == 1:
        return None, qname
    return parts


class Element:
    """One element in a document."""

    indent_amount = 4

    def __init__(self, qname, attrs=None, text=None):
        """Create instance with this QName and attrs."""
        self.qname = qname
        self.attrs = attrs
        self.text = text or ""
        self.tail = None
        self.child_elements = []

    def add_child(self, qname, attrs=None, text=None):
        """Create a new element and make it a child of this one."""
        elt = Element(qname, attrs, text)
        self.child_elements.append(elt)
        return elt

    def add_prefixes_used(self, prefix_namespaces, prefixes):
        """Return list of prefixes used by this element, its attributes and child elements."""
        prefix, _ = split_qname(self.qname)
        if prefix:
            prefixes.add(prefix)
        elif "" in prefix_namespaces:
            prefixes.add("")
        for child in self.child_elements:
            child.add_prefixes_used(prefix_namespaces, prefixes)
        return prefixes

    def sax_to(self, handler, prefix_namespaces, indent=0):
        """‘Parse’ this element to this handler.

        This is used to render the document by
        targeting an XMLGenerator instance.
        """
        attributes_ns = (
            {
                expand_qname(qname, prefix_namespaces): value
                for qname, value in self.attrs.items()
            }
            if self.attrs
            else {}
        )
        namespace_url, lname = expand_qname(self.qname, prefix_namespaces)
        if indent:
            handler.ignorableWhitespace("\n" + " " * (self.indent_amount * indent))
        handler.startElementNS((namespace_url, lname), self.qname, attributes_ns)
        if self.text:
            handler.characters(self.text)
        for elt in self.child_elements:
            elt.sax_to(handler, prefix_namespaces, indent + 1)
        if self.child_elements:
            handler.ignorableWhitespace("\n" + " " * (self.indent_amount * indent))
        handler.endElementNS((namespace_url, lname), self.qname)
        if self.tail:
            handler.characters(self.tail)


class Document(Element):
    """A blob of XML to be written to a file."""

    prefix_namespaces = {
        "xml": "http://www.w3.org/XML/1998/namespace",
    }

    def __init__(self, qname, attrs=None, text=None, prefix_namespaces=None):
        """Create document with the specified root element and known namespaces.

        Arguments --
            qname -- qualified name of the root element
            attrs -- attributes of the root element (no need to include XML namespace attributes)
            text -- charater data at the start of the root element
            prefix_namespaces -- map from prefix to namespace URI

        Note that all namespaces used (or that might be used) must be declared in advance!
        Namespaces not used by elements will not be passed to the XML writer.
        To set a default namespace for the document, create an antry for `''`.
        """
        super().__init__(qname, attrs, text)
        if prefix_namespaces:
            self.prefix_namespaces = dict(Document.prefix_namespaces)
            self.prefix_namespaces.update(prefix_namespaces)

    def write_to(self, output):
        """Write indented XML to this file-like object."""
        generator = XMLGenerator(output, "UTF-8", short_empty_elements=True)
        generator.startDocument()

        prefixes_used = list(self.add_prefixes_used(self.prefix_namespaces, set()))
        prefixes_used.sort()
        for prefix in prefixes_used:
            generator.startPrefixMapping(prefix, self.prefix_namespaces[prefix])
        self.sax_to(generator, prefix_namespaces=self.prefix_namespaces)
        for prefix in reversed(prefixes_used):
            generator.endPrefixMapping(prefix)
        generator.endDocument()
