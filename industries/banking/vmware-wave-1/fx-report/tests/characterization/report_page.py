"""Parse an fx-report page into the values the desk reads, independent of markup."""
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

BUSINESS_LINE = re.compile(r"^Business date (?P<date>.*), user (?P<user>.*)$")


@dataclass
class ReportPage:
    title: str = ""
    heading: str = ""
    business_line: str = ""
    business_date: str = ""
    user: str = ""
    empty_message: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.headings: list[str] = []
        self.paragraphs: list[str] = []
        self.header_cells: list[str] = []
        self.rows: list[list[str]] = []
        self._tag = None
        self._buf: list[str] = []
        self._row: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag in ("title", "h1", "p", "th", "td"):
            self._tag, self._buf = tag, []
        elif tag == "tr":
            self._row = []

    def handle_endtag(self, tag):
        if tag == "tr":
            if self._row:
                self.rows.append(self._row)
            self._row = None
            return
        if tag != self._tag:
            return
        text = " ".join("".join(self._buf).split())
        if tag == "title":
            self.title = text
        elif tag == "h1":
            self.headings.append(text)
        elif tag == "p":
            self.paragraphs.append(text)
        elif tag == "th":
            self.header_cells.append(text)
        elif tag == "td" and self._row is not None:
            self._row.append(text)
        self._tag = None

    def handle_data(self, data):
        if self._tag:
            self._buf.append(data)


def parse(html: str) -> ReportPage:
    p = _Parser()
    p.feed(html)
    p.close()
    page = ReportPage(title=p.title, heading=p.headings[0] if p.headings else "",
                      columns=p.header_cells, rows=p.rows)
    rest = []
    for text in p.paragraphs:
        m = BUSINESS_LINE.match(text)
        if m and not page.business_line:
            page.business_line = text
            page.business_date, page.user = m["date"], m["user"]
        else:
            rest.append(text)
    page.empty_message = rest[0] if rest else None
    return page
