import re

meta_open = re.compile(rb"<[mM][eE][tT][aA][\t\n\f\r /]")
other_open = re.compile(rb"</?[A-Za-z][^\t\n\f\r >]*")


def determine_encoding(input: bytes) -> tuple[str, bool]:
    """Prescan the initial portion of a byte stream looking for an HTML5 encoding.

    Implementing the whole fiddly algorithm is probably overkill but what the hey.

    https://html.spec.whatwg.org/multipage/parsing.html#prescan-a-byte-stream-to-determine-its-encoding
    """

    pos = 0
    while pos < len(input):
        if m := meta_open.match(input, pos):
            pos = m.end()
            attrs_seen = set()
            got_pragma = False
            need_pragma = None
            charset = None
            while True:
                attr, value, pos = get_attribute(input, pos)
                if not attr:
                    break
                if attr in attrs_seen:
                    continue
                attrs_seen.add(attr)
                match attr:
                    case b"http-equiv":
                        if value == b"content-type":
                            got_pragma = True
                    case b"content":
                        encoding = extract_encoding(value)
                        if encoding and charset is None:
                            charset = encoding
                            need_pragma = True
                    case b"charset":
                        charset = normalize_encoding(value)
                        need_pragma = False
            if (need_pragma is False or got_pragma) and charset:
                if charset in ("UTF-16BE", "UTF-16LE"):
                    charset = "UTF-8"
                elif charset == "x-user-defined":
                    charset = "windows-1252"
                return charset, True
        elif m := other_open.match(input, pos):
            pos = m.end()
            while True:
                attr, value, pos = get_attribute(input, pos)
                if not attr:
                    break
        else:
            pos += 1

    return "windows-1252", False


GT = ord(b">")
spaces_or_slashes = re.compile(rb"[\t\n\f\r /]+")
endtag_re = re.compile(rb"/?>")
name_re = re.compile(rb"=?[^\t\n\f\r =/>]*")
eq_spaces_re = re.compile(rb"[\t\n\f\r ]*=[\t\n\f\r ]*")
quoted_re = re.compile(rb"'[^']*'|" rb'"[^"]*"')
naked_re = re.compile(rb"[^\t\n\f\r >]*")


def get_attribute(input: bytes, pos: int) -> tuple[str, str, int]:
    """Scan an attribute starting at this position."""
    if m := spaces_or_slashes.match(input, pos):
        pos = m.end()
    if pos == len(input):
        return None, None, pos
    if input[pos] == GT:
        # This indicates we have finished scanning tag, so consume the `>`
        return None, None, pos + 1

    # We are at start of name
    m = name_re.match(input, pos)
    name = m[0].lower()
    pos = m.end()

    # We have scanned name and should be looking at an `=`
    if m := eq_spaces_re.match(input, pos):
        pos = m.end()
    else:
        # Was in fact looking atg end of input
        return name, b"", pos

    # Scanning the value
    if m := quoted_re.match(input, pos):
        value = input[pos + 1 : m.end() - 1].lower()
        return name, value, m.end()
    m = naked_re.match(input, pos)
    return name, m[0].lower(), m.end()


def normalize_encoding(input: bytes) -> str:
    """Given a token used in a HTML page (bytes), return the encoding (str)."""
    return encoding_lookup.get(input.lower())


charset_re = re.compile(rb"charset", re.IGNORECASE)
naked_encoding_re = re.compile(rb"[^\t\n\f\r ;]*")


def extract_encoding(input: bytes) -> str | None:
    """Find the encoding in the content of a meta tag.

    Look for charset="something" in the input text.
    """
    pos = 0
    while m := charset_re.search(input, pos):
        pos = m.end()
        if m := eq_spaces_re.match(input, pos):
            pos = m.end()
            if m := quoted_re.match(input, pos):
                return normalize_encoding(input[pos + 1 : m.end() - 1])
            m = naked_encoding_re.match(input, pos)
            return normalize_encoding(m[0])


# https://encoding.spec.whatwg.org/encodings.json
encoding_json = [
    {
        "encodings": [
            {
                "labels": [
                    "unicode-1-1-utf-8",
                    "unicode11utf8",
                    "unicode20utf8",
                    "utf-8",
                    "utf8",
                    "x-unicode20utf8",
                ],
                "name": "UTF-8",
            }
        ],
        "heading": "The Encoding",
    },
    {
        "encodings": [
            {"labels": ["866", "cp866", "csibm866", "ibm866"], "name": "IBM866"},
            {
                "labels": [
                    "csisolatin2",
                    "iso-8859-2",
                    "iso-ir-101",
                    "iso8859-2",
                    "iso88592",
                    "iso_8859-2",
                    "iso_8859-2:1987",
                    "l2",
                    "latin2",
                ],
                "name": "ISO-8859-2",
            },
            {
                "labels": [
                    "csisolatin3",
                    "iso-8859-3",
                    "iso-ir-109",
                    "iso8859-3",
                    "iso88593",
                    "iso_8859-3",
                    "iso_8859-3:1988",
                    "l3",
                    "latin3",
                ],
                "name": "ISO-8859-3",
            },
            {
                "labels": [
                    "csisolatin4",
                    "iso-8859-4",
                    "iso-ir-110",
                    "iso8859-4",
                    "iso88594",
                    "iso_8859-4",
                    "iso_8859-4:1988",
                    "l4",
                    "latin4",
                ],
                "name": "ISO-8859-4",
            },
            {
                "labels": [
                    "csisolatincyrillic",
                    "cyrillic",
                    "iso-8859-5",
                    "iso-ir-144",
                    "iso8859-5",
                    "iso88595",
                    "iso_8859-5",
                    "iso_8859-5:1988",
                ],
                "name": "ISO-8859-5",
            },
            {
                "labels": [
                    "arabic",
                    "asmo-708",
                    "csiso88596e",
                    "csiso88596i",
                    "csisolatinarabic",
                    "ecma-114",
                    "iso-8859-6",
                    "iso-8859-6-e",
                    "iso-8859-6-i",
                    "iso-ir-127",
                    "iso8859-6",
                    "iso88596",
                    "iso_8859-6",
                    "iso_8859-6:1987",
                ],
                "name": "ISO-8859-6",
            },
            {
                "labels": [
                    "csisolatingreek",
                    "ecma-118",
                    "elot_928",
                    "greek",
                    "greek8",
                    "iso-8859-7",
                    "iso-ir-126",
                    "iso8859-7",
                    "iso88597",
                    "iso_8859-7",
                    "iso_8859-7:1987",
                    "sun_eu_greek",
                ],
                "name": "ISO-8859-7",
            },
            {
                "labels": [
                    "csiso88598e",
                    "csisolatinhebrew",
                    "hebrew",
                    "iso-8859-8",
                    "iso-8859-8-e",
                    "iso-ir-138",
                    "iso8859-8",
                    "iso88598",
                    "iso_8859-8",
                    "iso_8859-8:1988",
                    "visual",
                ],
                "name": "ISO-8859-8",
            },
            {
                "labels": ["csiso88598i", "iso-8859-8-i", "logical"],
                "name": "ISO-8859-8-I",
            },
            {
                "labels": [
                    "csisolatin6",
                    "iso-8859-10",
                    "iso-ir-157",
                    "iso8859-10",
                    "iso885910",
                    "l6",
                    "latin6",
                ],
                "name": "ISO-8859-10",
            },
            {
                "labels": ["iso-8859-13", "iso8859-13", "iso885913"],
                "name": "ISO-8859-13",
            },
            {
                "labels": ["iso-8859-14", "iso8859-14", "iso885914"],
                "name": "ISO-8859-14",
            },
            {
                "labels": [
                    "csisolatin9",
                    "iso-8859-15",
                    "iso8859-15",
                    "iso885915",
                    "iso_8859-15",
                    "l9",
                ],
                "name": "ISO-8859-15",
            },
            {"labels": ["iso-8859-16"], "name": "ISO-8859-16"},
            {
                "labels": ["cskoi8r", "koi", "koi8", "koi8-r", "koi8_r"],
                "name": "KOI8-R",
            },
            {"labels": ["koi8-ru", "koi8-u"], "name": "KOI8-U"},
            {
                "labels": ["csmacintosh", "mac", "macintosh", "x-mac-roman"],
                "name": "macintosh",
            },
            {
                "labels": [
                    "dos-874",
                    "iso-8859-11",
                    "iso8859-11",
                    "iso885911",
                    "tis-620",
                    "windows-874",
                ],
                "name": "windows-874",
            },
            {"labels": ["cp1250", "windows-1250", "x-cp1250"], "name": "windows-1250"},
            {"labels": ["cp1251", "windows-1251", "x-cp1251"], "name": "windows-1251"},
            {
                "labels": [
                    "ansi_x3.4-1968",
                    "ascii",
                    "cp1252",
                    "cp819",
                    "csisolatin1",
                    "ibm819",
                    "iso-8859-1",
                    "iso-ir-100",
                    "iso8859-1",
                    "iso88591",
                    "iso_8859-1",
                    "iso_8859-1:1987",
                    "l1",
                    "latin1",
                    "us-ascii",
                    "windows-1252",
                    "x-cp1252",
                ],
                "name": "windows-1252",
            },
            {"labels": ["cp1253", "windows-1253", "x-cp1253"], "name": "windows-1253"},
            {
                "labels": [
                    "cp1254",
                    "csisolatin5",
                    "iso-8859-9",
                    "iso-ir-148",
                    "iso8859-9",
                    "iso88599",
                    "iso_8859-9",
                    "iso_8859-9:1989",
                    "l5",
                    "latin5",
                    "windows-1254",
                    "x-cp1254",
                ],
                "name": "windows-1254",
            },
            {"labels": ["cp1255", "windows-1255", "x-cp1255"], "name": "windows-1255"},
            {"labels": ["cp1256", "windows-1256", "x-cp1256"], "name": "windows-1256"},
            {"labels": ["cp1257", "windows-1257", "x-cp1257"], "name": "windows-1257"},
            {"labels": ["cp1258", "windows-1258", "x-cp1258"], "name": "windows-1258"},
            {"labels": ["x-mac-cyrillic", "x-mac-ukrainian"], "name": "x-mac-cyrillic"},
        ],
        "heading": "Legacy single-byte encodings",
    },
    {
        "encodings": [
            {
                "labels": [
                    "chinese",
                    "csgb2312",
                    "csiso58gb231280",
                    "gb2312",
                    "gb_2312",
                    "gb_2312-80",
                    "gbk",
                    "iso-ir-58",
                    "x-gbk",
                ],
                "name": "GBK",
            },
            {"labels": ["gb18030"], "name": "gb18030"},
        ],
        "heading": "Legacy multi-byte Chinese (simplified) encodings",
    },
    {
        "encodings": [
            {
                "labels": ["big5", "big5-hkscs", "cn-big5", "csbig5", "x-x-big5"],
                "name": "Big5",
            }
        ],
        "heading": "Legacy multi-byte Chinese (traditional) encodings",
    },
    {
        "encodings": [
            {"labels": ["cseucpkdfmtjapanese", "euc-jp", "x-euc-jp"], "name": "EUC-JP"},
            {"labels": ["csiso2022jp", "iso-2022-jp"], "name": "ISO-2022-JP"},
            {
                "labels": [
                    "csshiftjis",
                    "ms932",
                    "ms_kanji",
                    "shift-jis",
                    "shift_jis",
                    "sjis",
                    "windows-31j",
                    "x-sjis",
                ],
                "name": "Shift_JIS",
            },
        ],
        "heading": "Legacy multi-byte Japanese encodings",
    },
    {
        "encodings": [
            {
                "labels": [
                    "cseuckr",
                    "csksc56011987",
                    "euc-kr",
                    "iso-ir-149",
                    "korean",
                    "ks_c_5601-1987",
                    "ks_c_5601-1989",
                    "ksc5601",
                    "ksc_5601",
                    "windows-949",
                ],
                "name": "EUC-KR",
            }
        ],
        "heading": "Legacy multi-byte Korean encodings",
    },
    {
        "encodings": [
            {
                "labels": [
                    "csiso2022kr",
                    "hz-gb-2312",
                    "iso-2022-cn",
                    "iso-2022-cn-ext",
                    "iso-2022-kr",
                    "replacement",
                ],
                "name": "replacement",
            },
            {"labels": ["unicodefffe", "utf-16be"], "name": "UTF-16BE"},
            {
                "labels": [
                    "csunicode",
                    "iso-10646-ucs-2",
                    "ucs-2",
                    "unicode",
                    "unicodefeff",
                    "utf-16",
                    "utf-16le",
                ],
                "name": "UTF-16LE",
            },
            {"labels": ["x-user-defined"], "name": "x-user-defined"},
        ],
        "heading": "Legacy miscellaneous encodings",
    },
]

# Map from the token used in web pages (bytes) to the encoding name (str)
encoding_lookup: dict[bytes, str] = {
    label.encode("ascii"): encoding["name"]
    for section in encoding_json
    for encoding in section["encodings"]
    for label in encoding["labels"]
}
