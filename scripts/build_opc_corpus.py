from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "src" / "westminster_cli" / "data" / "standards.json"


@dataclass
class Block:
    kind: str
    text: str


class MainBlockParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_main = False
        self.main_depth = 0
        self.dir_depth = 0
        self.current_kind: Optional[str] = None
        self.current_parts: list[str] = []
        self.blocks: list[Block] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        attrs_map = dict(attrs)
        classes = set((attrs_map.get("class") or "").split())
        if tag == "div" and "mainBlock" in classes and not self.in_main:
            self.in_main = True
            self.main_depth = 1
            return

        if not self.in_main:
            return

        if tag == "div":
            self.main_depth += 1
        elif tag == "dir":
            # Suggested liturgical forms: keep as prose, not outline structure.
            self.dir_depth += 1
        elif tag in {"p", "h1", "h3", "td"}:
            self._flush()
            # Paragraphs inside <dir> are form text; tag them as "form".
            self.current_kind = "form" if self.dir_depth > 0 and tag == "p" else tag
            self.current_parts = []
        elif tag == "br" and self.current_kind:
            self.current_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if not self.in_main:
            return

        if tag == "dir":
            self.dir_depth = max(0, self.dir_depth - 1)
            return

        if tag in {"p", "h1", "h3", "td"} and self.current_kind in {tag, "form"}:
            self._flush()
        elif tag == "div":
            self.main_depth -= 1
            if self.main_depth <= 0:
                self._flush()
                self.in_main = False

    def handle_data(self, data: str) -> None:
        if self.in_main and self.current_kind:
            self.current_parts.append(data)

    def _flush(self) -> None:
        if not self.current_kind:
            return
        text = normalize(" ".join("".join(self.current_parts).split()))
        if text:
            self.blocks.append(Block(self.current_kind, text))
        self.current_kind = None
        self.current_parts = []


def normalize(value: str) -> str:
    return (
        value.replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u00a0", " ")
        .strip()
    )


def parse_blocks(path: Path) -> list[Block]:
    parser = MainBlockParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.blocks


def parse_catechism(path: Path, doc_id: str, title: str, short_title: str, source_url: str) -> dict:
    entries = []
    for block in parse_blocks(path):
        if block.kind != "p":
            continue
        match = re.match(r"^Q\. (\d+)\. (.*?) A\. (.*)$", block.text)
        if not match:
            continue
        ref, question, answer = match.groups()
        entries.append(
            {
                "ref": ref,
                "kind": "qa",
                "question": question.strip(),
                "answer": answer.strip(),
            }
        )

    return {
        "id": doc_id,
        "title": title,
        "short_title": short_title,
        "source": "Orthodox Presbyterian Church constitutional text",
        "source_url": source_url,
        "entries": entries,
    }


def parse_wcf(path: Path) -> dict:
    entries = []
    current_chapter: Optional[str] = None
    current_heading: Optional[str] = None
    current_entry: Optional[dict] = None

    def flush_current() -> None:
        nonlocal current_entry
        if current_entry is not None:
            current_entry["text"] = " ".join(current_entry["text_parts"]).strip()
            del current_entry["text_parts"]
            entries.append(current_entry)
            current_entry = None

    for block in parse_blocks(path):
        if block.kind == "h3":
            flush_current()
            match = re.match(r"^CHAPTER (\d+) (.+)$", block.text)
            if match:
                current_chapter, current_heading = match.groups()
            continue

        if current_chapter is None or block.kind not in {"p", "td"}:
            continue

        numbered = re.match(r"^(\d+)\. (.*)$", block.text)
        if block.kind == "p" and numbered:
            flush_current()
            paragraph, text = numbered.groups()
            current_entry = {
                "ref": f"{int(current_chapter)}.{paragraph}",
                "kind": "section",
                "heading": current_heading,
                "text_parts": [text],
            }
        elif current_entry is not None:
            current_entry["text_parts"].append(block.text)

    flush_current()
    return {
        "id": "wcf",
        "title": "Westminster Confession of Faith",
        "short_title": "Confession of Faith",
        "source": "Orthodox Presbyterian Church constitutional text",
        "source_url": "https://opc.org/wcf.html",
        "entries": entries,
    }


def parse_dpw(path: Path) -> dict:
    """Parse the OPC Directory for the Public Worship of God.

    Entries use hierarchical refs under each chapter and lettered section:
    preface, 1.A.1, 1.A.1.a, 3.B.1.b.1, and so on. Unnumbered prose after a
    heading is folded into the preceding entry (or a chapter intro entry).
    """
    entries: list[dict] = []
    chapter: Optional[str] = None
    chapter_title: Optional[str] = None
    section_letter: Optional[str] = None
    section_title: Optional[str] = None
    # Numbering components after the lettered section, e.g. ["1", "a", "2"]
    num_path: list[str] = []
    current: Optional[dict] = None
    in_preface = False
    preface_parts: list[str] = []

    chapter_re = re.compile(r"^CHAPTER ([IVXLC]+)\s+(.*)$", re.IGNORECASE)
    section_re = re.compile(r"^([A-Z])\.\s+(.*)$")
    numbered_re = re.compile(r"^(\d+)\.\s+(.*)$")
    lettered_re = re.compile(r"^([a-z])\.\s+(.*)$")
    paren_re = re.compile(r"^\((\d+)\)\s+(.*)$")

    def heading_for() -> str:
        parts: list[str] = []
        if chapter_title:
            parts.append(chapter_title)
        if section_title:
            parts.append(section_title)
        return " · ".join(parts) if parts else "Directory for Public Worship"

    def flush() -> None:
        nonlocal current
        if current is not None:
            current["text"] = " ".join(current["text_parts"]).strip()
            del current["text_parts"]
            if current["text"] or current.get("heading"):
                entries.append(current)
            current = None

    def start_entry(ref: str, lead: str = "") -> None:
        nonlocal current
        flush()
        current = {
            "ref": ref,
            "kind": "section",
            "heading": heading_for(),
            "text_parts": [lead] if lead else [],
        }

    def ref_from_path() -> str:
        assert chapter is not None and section_letter is not None
        return f"{chapter}.{section_letter}." + ".".join(num_path)

    def roman_to_int(value: str) -> int:
        values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
        total = 0
        prev = 0
        for char in value.upper():
            current_val = values[char]
            total += current_val
            if current_val > prev:
                total -= 2 * prev
            prev = current_val
        return total

    for block in parse_blocks(path):
        if block.kind == "h3":
            if block.text == "Preface":
                flush()
                in_preface = True
                preface_parts = []
                chapter = None
                section_letter = None
                num_path = []
                continue

            chapter_match = chapter_re.match(block.text)
            if chapter_match:
                flush()
                if in_preface and preface_parts:
                    entries.append(
                        {
                            "ref": "preface",
                            "kind": "section",
                            "heading": "Preface",
                            "text": " ".join(preface_parts).strip(),
                        }
                    )
                    preface_parts = []
                in_preface = False
                roman, title = chapter_match.groups()
                chapter = str(roman_to_int(roman))
                chapter_title = title.strip()
                section_letter = None
                section_title = None
                num_path = []
                continue

            section_match = section_re.match(block.text)
            if section_match and chapter is not None:
                flush()
                in_preface = False
                section_letter, section_title = section_match.groups()
                section_title = section_title.strip()
                num_path = []
                continue

            # Unrecognized heading: treat as prose continuation if possible.
            if current is not None:
                current["text_parts"].append(block.text)
            continue

        if block.kind == "form":
            # Suggested liturgical wording: fold into the current entry.
            if in_preface:
                preface_parts.append(block.text)
            elif current is not None:
                current["text_parts"].append(block.text)
            continue

        if block.kind != "p":
            continue

        if in_preface:
            preface_parts.append(block.text)
            continue

        if chapter is None:
            continue

        numbered = numbered_re.match(block.text)
        lettered = lettered_re.match(block.text)
        paren = paren_re.match(block.text)

        if numbered and section_letter is not None:
            num, rest = numbered.groups()
            num_path = [num]
            start_entry(ref_from_path(), rest.strip())
            continue

        if lettered and section_letter is not None and num_path:
            # Sibling under the current top-level number: keep only the first
            # component, then the letter (e.g. 1.a under ["1", ...] -> ["1","a"]).
            letter, rest = lettered.groups()
            num_path = [num_path[0], letter]
            start_entry(ref_from_path(), rest.strip())
            continue

        if paren and section_letter is not None and num_path:
            num, rest = paren.groups()
            # Sibling parentheticals replace a trailing digit; otherwise append.
            if num_path[-1].isdigit():
                num_path = num_path[:-1] + [num]
            else:
                num_path = num_path + [num]
            start_entry(ref_from_path(), rest.strip())
            continue

        # Unnumbered prose / liturgical form text: chapter intro, or continuation.
        if section_letter is None:
            if current is not None and current["ref"] == f"{chapter}.intro":
                current["text_parts"].append(block.text)
            else:
                flush()
                current = {
                    "ref": f"{chapter}.intro",
                    "kind": "section",
                    "heading": chapter_title or f"Chapter {chapter}",
                    "text_parts": [block.text],
                }
            continue

        if current is not None:
            current["text_parts"].append(block.text)
        elif num_path:
            start_entry(ref_from_path(), block.text)
        else:
            # Prose under a lettered section with no numbered item yet.
            start_entry(f"{chapter}.{section_letter}", block.text)

    flush()
    if in_preface and preface_parts:
        entries.append(
            {
                "ref": "preface",
                "kind": "section",
                "heading": "Preface",
                "text": " ".join(preface_parts).strip(),
            }
        )

    return {
        "id": "dpw",
        "title": "Directory for the Public Worship of God",
        "short_title": "Directory for Public Worship",
        "source": "Orthodox Presbyterian Church Book of Church Order",
        "source_url": "https://opc.org/BCO/DPW.html",
        "entries": entries,
    }


def build(wcf: Path, lc: Path, sc: Path, dpw: Optional[Path] = None) -> dict:
    documents = [
        parse_wcf(wcf),
        parse_catechism(
            lc,
            "wlc",
            "Westminster Larger Catechism",
            "Larger Catechism",
            "https://opc.org/lc.html",
        ),
        parse_catechism(
            sc,
            "wsc",
            "Westminster Shorter Catechism",
            "Shorter Catechism",
            "https://opc.org/sc.html",
        ),
    ]
    if dpw is not None:
        documents.append(parse_dpw(dpw))
    return {
        "source": "Orthodox Presbyterian Church Confession, Catechisms, and Directory for Public Worship",
        "source_url": "https://opc.org/standards.html",
        "documents": documents,
    }


def main(argv: list[str]) -> int:
    if len(argv) not in {4, 5}:
        print(
            "usage: build_opc_corpus.py WCF_HTML LC_HTML SC_HTML [DPW_HTML]",
            file=sys.stderr,
        )
        return 2

    dpw = Path(argv[4]) if len(argv) == 5 else None
    corpus = build(Path(argv[1]), Path(argv[2]), Path(argv[3]), dpw)
    OUTPUT.write_text(json.dumps(corpus, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for document in corpus["documents"]:
        print(f"{document['id']}: {len(document['entries'])} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
