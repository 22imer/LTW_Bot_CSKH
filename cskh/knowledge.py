"""Retrieval for RAG: chunk the shop's text files and rank chunks for a query.

Keyword retrieval (SQLite FTS5, BM25) on accent-folded text, so "tra dao" finds "Trà Đào".
It matches words, not meaning: "thanh mát" will not find "trà" unless the words overlap.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass

# Words that appear in almost every question and would match unrelated chunks.
STOPWORDS = frozenset({
    "la", "co", "khong", "gi", "nao", "the", "nay", "kia", "va", "hay", "hoac", "cua", "cho",
    "minh", "ban", "toi", "em", "anh", "chi", "oi", "nhe", "a", "voi", "duoc", "bi", "o", "tai",
    "thi", "ma", "de", "da", "dang", "se", "muon", "can", "xin", "hoi", "cai", "mot", "nhung",
    "cac", "may", "bao", "nhieu", "quan",
})
# Common spellings that differ from the menu's wording after folding.
SYNONYMS = {
    "cafe": ("ca", "phe"),
    "caphe": ("ca", "phe"),
    "coffee": ("ca", "phe"),
    "cf": ("ca", "phe"),
    "ship": ("giao", "hang"),
    "delivery": ("giao", "hang"),
    "wifi": ("wifi",),
}
_ITEM = re.compile(r"^(\d+\.|-)\s+")


def fold(text: str) -> str:
    """Lowercase and strip Vietnamese accents (including đ -> d)."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return stripped.replace("đ", "d")


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for word in re.findall(r"[a-z0-9]+", fold(text)):
        if word in STOPWORDS:
            continue
        tokens.extend(SYNONYMS.get(word, (word,)))
    return tokens


@dataclass(frozen=True)
class Chunk:
    source: str  # "menu" or "faq"
    text: str


def chunk_menu(menu_text: str) -> list[Chunk]:
    """One chunk per menu item or topping, prefixed with its category."""
    chunks: list[Chunk] = []
    category = ""
    for raw in menu_text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            category = line[3:].strip()
        elif line.startswith("- "):
            chunks.append(Chunk("menu", f"{category}: {line[2:].strip()}" if category else line[2:].strip()))
    return chunks


def chunk_faq(faq_text: str) -> list[Chunk]:
    """One chunk per list item (with its section heading) or per standalone paragraph line."""
    lines = [line.strip() for line in faq_text.splitlines() if line.strip()]
    chunks: list[Chunk] = []
    heading = ""
    for index, line in enumerate(lines):
        if _ITEM.match(line):
            body = _ITEM.sub("", line)
            chunks.append(Chunk("faq", f"{heading}: {body}" if heading else body))
            continue
        next_is_item = index + 1 < len(lines) and bool(_ITEM.match(lines[index + 1]))
        if next_is_item:
            heading = line
        else:
            heading = ""
            chunks.append(Chunk("faq", line))
    return chunks


class KnowledgeBase:
    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks
        self._db = sqlite3.connect(":memory:")
        self._db.execute("CREATE VIRTUAL TABLE idx USING fts5(text, tokenize='unicode61')")
        self._db.executemany(
            "INSERT INTO idx(rowid, text) VALUES (?, ?)",
            [(i, " ".join(tokenize(c.text))) for i, c in enumerate(chunks)],
        )

    @classmethod
    def from_texts(cls, faq_text: str, menu_text: str) -> KnowledgeBase:
        return cls([*chunk_faq(faq_text), *chunk_menu(menu_text)])

    def __len__(self) -> int:
        return len(self._chunks)

    def search(self, query: str, limit: int = 5) -> list[Chunk]:
        """Best-matching chunks first. Matches any query word; BM25 ranks rarer words higher."""
        tokens = list(dict.fromkeys(tokenize(query)))
        if not tokens:
            return []
        match = " OR ".join(f'"{token}"' for token in tokens)
        rows = self._db.execute(
            "SELECT rowid FROM idx WHERE idx MATCH ? ORDER BY bm25(idx) LIMIT ?", (match, limit)
        ).fetchall()
        return [self._chunks[row[0]] for row in rows]
