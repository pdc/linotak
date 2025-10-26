"""Scan the MIME type of a request in the most paranoid fashion.

See https://mimesniff.spec.whatwg.org

Our requirements are fairly limited. For scannign wseb pages we care about
(1) is it HTML (or XML, hopefully XHTML)?
(2) what is its encoding (charset)?

"""

import re
from dataclasses import dataclass, field

http_ws_re = re.compile(rb"[\n\r\t ]*")
http_token_re = re.compile(rb"[!#$%&'*+^_`|~a-zA-Z0-9.-]+")
http_quoted_re = re.compile(rb"[\t -~\x80-\xFF]*")
not_slash_re = re.compile(rb"[^/]*")
not_semi_re = re.compile(rb"[^;]*")
not_semi_eq_re = re.compile(rb"[^=;]*")
not_qt_bslash_re = re.compile(rb'[^"\\]*')
not_ws_re = re.compile(rb"[^\t\n\r ]*")
trailing_ws_re = re.compile(rb"[\n\r\t ]+$")
SEMI, EQ, QT, BS = b';="\\'


@dataclass(slots=True)
class MimeType:
    type: str
    subtype: str
    parameters: dict[str, str] = field(default_factory=dict)

    @property
    def essence(self):
        return f"{self.type}/{self.subtype}"

    @classmethod
    def parse(cls, input: bytes) -> "MimeType":
        """Given the raw bytes of a Content-Type header, return a MIME type or None.

        The header should be passed as bytes from the server. The result will
        converted to strings.
        """
        # Skip initial whitespace (1–2)
        pos = http_ws_re.match(input).end()

        # Scan type (3–5)
        m = not_slash_re.match(input, pos)
        type, pos = m[0], m.end()
        if not http_token_re.fullmatch(type) or pos == len(input):
            return

        # Scan subtype (6–9)
        pos += 1  # Skip slash
        m = not_semi_re.match(input, pos)
        subtype, pos = m[0], m.end()
        # Must be token (with optional trailing wehitespace).
        m = http_token_re.match(subtype)
        if not m or not http_ws_re.fullmatch(subtype, m.end()):
            return
        subtype = m[0]

        result = MimeType(type.lower().decode("ascii"), subtype.lower().decode("ascii"))
        # Scan paramerters (11)
        while pos < len(input):
            pos += 1  # Skip semicolon
            pos = http_ws_re.match(input, pos).end()
            m = not_semi_eq_re.match(input, pos)
            name, pos = m[0], m.end()
            if pos == len(input):
                break
            if input[pos] == SEMI:
                continue
            pos += 1  # Skip eq
            if pos == len(input):
                break
            if input[pos] == QT:
                # Collect an HTTP quoted string
                value = b""
                pos += 1  # Skip quote
                # Scan quoted value, allowing for backslash escapes.
                while pos < len(input):
                    m = not_qt_bslash_re.match(input, pos)
                    value += m[0]
                    pos = m.end()
                    if pos == len(input):
                        break
                    if input[pos] == QT:
                        pos += 1  # Skip closing quote
                        break
                    pos += 1  # Skip backslash
                    if pos == len(input):
                        value += BS
                        break
            else:
                # Unquoted value (11.9)
                m = not_semi_re.match(input, pos)
                value, pos = m[0], m.end()
                # Strip whitespace from end – even if there is embedded whitespace sigh
                if m := trailing_ws_re.search(value):
                    value = value[: m.start()]
                if not value:
                    continue
            if http_token_re.fullmatch(name) and http_quoted_re.fullmatch(value):
                result.parameters.setdefault(
                    name.lower().decode("ascii"),
                    value.decode("ascii", errors="replace"),
                )

        return result
