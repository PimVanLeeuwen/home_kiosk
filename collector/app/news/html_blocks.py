"""Readeck's article HTML to the reader's plain blocks.

Readeck already cleans what it stores, but the browser still gets text only:
the same Block shapes as reader.py, with no markup. Images are listed by
position so the hub can proxy them.
"""

from __future__ import annotations

from html.parser import HTMLParser

from .reader import Block

HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
# Elements whose text becomes one block of the given kind.
BLOCKS = {**dict.fromkeys(HEADINGS, "heading"), "p": "paragraph", "pre": "paragraph",
          "tr": "paragraph", "figcaption": "paragraph", "dd": "paragraph", "dt": "paragraph"}
SKIP = {"script", "style", "template", "svg", "noscript", "iframe", "object"}


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[Block] = []
        self.images: list[str] = []
        self.kinds: list[str] = []  # open block elements, innermost last
        self.quote = 0  # inside how many blockquotes
        self.lists = 0  # inside how many ul/ol
        self.skip = 0
        self.items: list[str] = []
        self.buffer: list[str] = []

    def _flush(self, kind: str | None = None) -> None:
        text = " ".join("".join(self.buffer).split())
        self.buffer = []
        if not text:
            return
        if self.lists and kind in (None, "item"):
            self.items.append(text)
        elif self.quote:
            self.blocks.append(Block(type="quote", text=text))
        else:
            self.blocks.append(Block(type="heading" if kind == "heading" else "paragraph",
                                     text=text))

    def _end_list(self) -> None:
        if self.items:
            self.blocks.append(Block(type="list", items=self.items))
        self.items = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        if tag in BLOCKS or tag in ("li", "blockquote", "ul", "ol"):
            self._flush(self.kinds[-1] if self.kinds else None)
        if tag in BLOCKS:
            self.kinds.append(BLOCKS[tag])
        elif tag == "li":
            self.kinds.append("item")
        elif tag == "blockquote":
            self.quote += 1
        elif tag in ("ul", "ol"):
            if not self.lists:
                self.items = []
            self.lists += 1
        elif tag in ("td", "th"):
            self.buffer.append(" · " if "".join(self.buffer).strip() else "")
        elif tag == "br":
            self.buffer.append(" ")
        elif tag == "img":
            src = dict(attrs).get("src") or ""
            if src.startswith(("http://", "https://", "/")):
                self._flush(self.kinds[-1] if self.kinds else None)
                self.images.append(src)
                self.blocks.append(Block(type="image", text=dict(attrs).get("alt") or "",
                                         src=str(len(self.images) - 1)))

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag in BLOCKS or tag == "li":
            kind = self.kinds.pop() if self.kinds else None
            self._flush(kind)
        elif tag == "blockquote":
            self._flush()
            self.quote = max(0, self.quote - 1)
        elif tag in ("ul", "ol"):
            self._flush("item")
            self.lists = max(0, self.lists - 1)
            if not self.lists:
                self._end_list()

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.buffer.append(data)

    def close(self) -> None:
        super().close()
        self._flush(self.kinds[-1] if self.kinds else None)
        if self.lists:
            self._end_list()


def to_blocks(html: str) -> tuple[list[Block], list[str]]:
    """Blocks and image URLs. Image blocks carry their position in `src`;
    the caller turns it into its own proxy URL."""
    parser = _Parser()
    parser.feed(html)
    parser.close()
    return parser.blocks, parser.images
