from __future__ import annotations

import textwrap

from .corpus import Document, Entry


# --- Reverent palette (24-bit; degrades to nothing when color is disabled) ---
# oxblood, gold, and a muted sepia. These read on both light and dark terminals.
OX = "38;2;176;74;58"        # oxblood accent
OX_B = "1;38;2;176;74;58"    # oxblood, bold
GOLD = "38;2;181;138;58"     # gilt / rule
GOLD_B = "1;38;2;181;138;58"
MUTE = "38;2;150;140;116"    # muted sepia
STRONG = "1"                 # bold in the terminal's own foreground (the "ink")

_FRAME_W = 64  # interior width of the illuminated frame


def _color(text: str, code: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"\033[{code}m{text}\033[0m"


def _center(text: str, width: int = _FRAME_W) -> tuple[str, str]:
    """Return (left_pad, right_pad) that center `text` within `width`."""
    left = (width - len(text)) // 2
    right = width - len(text) - left
    return " " * left, " " * right


def _home_banner(color: bool) -> list[str]:
    c = lambda t, code: _color(t, code, color)
    bar = c("═" * _FRAME_W, GOLD)
    side = lambda inner: c("║", GOLD) + inner + c("║", GOLD)

    # blank interior row
    blank = side(" " * _FRAME_W)

    # wordmark
    word = "W  E  S  T  M  I  N  S  T  E  R"
    lw, rw = _center(word)
    wordmark = side(lw + c(word, STRONG) + rw)

    # subtitle:  ❧   S T A N D A R D S   ❧
    sub_plain = "❧   S T A N D A R D S   ❧"
    ls, rs = _center(sub_plain)
    subtitle = side(
        ls + c("❧", OX) + "   " + c("S T A N D A R D S", MUTE) + "   " + c("❧", OX) + rs
    )

    # tagline
    tag = "Confession · Catechisms · Directory for Public Worship"
    lt, rt = _center(tag)
    tagline = side(lt + c(tag, MUTE) + rt)

    return [
        c("╔" + "═" * _FRAME_W + "╗", GOLD),
        blank,
        wordmark,
        subtitle,
        blank,
        tagline,
        blank,
        c("╚" + "═" * _FRAME_W + "╝", GOLD),
    ]


def format_home(documents: tuple[Document, ...], color: bool = False) -> str:
    c = lambda t, code: _color(t, code, color)
    total_entries = sum(len(document.entries) for document in documents)
    qa_count = sum(
        1 for document in documents for entry in document.entries if entry.kind == "qa"
    )

    def section(title: str) -> str:
        return c(title, OX_B)

    lines = [
        *_home_banner(color),
        "",
        "  "
        + c(f"{len(documents)} documents", GOLD)
        + " · "
        + c(f"{total_entries} entries", GOLD)
        + " · "
        + c(str(qa_count), GOLD)
        + " catechism Q/A",
        "",
        "  " + section("READ"),
        "    " + c("ws", OX) + " " + c("wsc 1", GOLD) + "              " + c("Shorter Catechism · question 1", MUTE),
        "    " + c("ws", OX) + " " + c("wcf 1.1", GOLD) + "            " + c("Confession · chapter 1, section 1", MUTE),
        "    " + c("ws", OX) + " " + c("dpw 1.A.1", GOLD) + "          " + c("Directory for Public Worship", MUTE),
        "    " + c("ws", OX) + " " + c("wsc 1 --answer", GOLD) + "     " + c("Reveal only the answer", MUTE),
        "    " + c("ws", OX) + " " + c("wsc 1 -p", GOLD) + "           " + c("With Scripture proof texts", MUTE),
        "    " + c("ws", OX) + " " + c("wsc 1 -m", GOLD) + "           " + c("2025 Modern English Study Version", MUTE),
        "    " + c("ws", OX) + " " + c("wsc 1 --compare", GOLD) + "    " + c("Constitutional and MESV together", MUTE),
        "",
        "  " + section("EXPLORE"),
        "    " + c("ws", OX) + " " + c("search", GOLD) + ' "chief end"',
        "    " + c("ws", OX) + " " + c("search --doc dpw", GOLD) + " baptism",
        "    " + c("ws", OX) + " " + c("quiz", GOLD) + " wsc 10",
        "",
        "  " + section("SYSTEM"),
        "    "
        + c("ws", OX) + " stats     "
        + c("ws", OX) + " sources     "
        + c("ws", OX) + " /     "
        + c("ws", OX) + " --help",
        "",
        "  " + c("ws>", OX),
    ]
    return "\n".join(lines)


def format_slash_commands(color: bool = False) -> str:
    c = lambda t, code: _color(t, code, color)
    lines = [
        c("SLASH COMMANDS", OX_B),
        c("─" * 54, GOLD),
        "",
        "  " + c("Read", OX_B),
        "    " + c("/wcf 1", GOLD) + "              Confession chapter 1",
        "    " + c("/wcf 1.1", GOLD) + "            Confession section 1.1",
        "    " + c("/wsc 1", GOLD) + "              Shorter Catechism question 1",
        "    " + c("/wlc 1", GOLD) + "              Larger Catechism question 1",
        "    " + c("/dpw 1.A.1", GOLD) + "          Directory for Public Worship",
        "    " + c("/q wsc 1", GOLD) + "            Print only a question",
        "    " + c("/a wsc 1", GOLD) + "            Print only an answer",
        "    " + c("/p wsc 1", GOLD) + "            With Scripture proof texts",
        "    " + c("/m wsc 1", GOLD) + "            Modern English (2025 MESV)",
        "",
        "  " + c("Explore", OX_B),
        "    " + c("/search", GOLD) + ' "chief end"',
        "    " + c("/search --doc dpw", GOLD) + " baptism",
        "    " + c("/list", GOLD) + " wcf",
        "    " + c("/quiz", GOLD) + " wsc 10",
        "",
        "  " + c("System", OX_B),
        "    " + c("/stats", GOLD),
        "    " + c("/sources", GOLD),
        "    " + c("/clear", GOLD),
        "    " + c("/help", GOLD),
    ]
    return "\n".join(lines)


def format_document_list(documents: tuple[Document, ...]) -> str:
    lines = ["Available documents:"]
    for document in documents:
        lines.append(f"  {document.id:<4} {document.title} ({len(document.entries)} entries)")
    return "\n".join(lines)


def format_entry_list(document: Document, color: bool = False) -> str:
    c = lambda t, code: _color(t, code, color)
    lines = [
        c(document.title, STRONG) + "   " + c(document.source_url, MUTE),
        c("─" * 60, GOLD),
        "",
    ]
    for entry in document.entries:
        if entry.kind == "qa":
            label = entry.question or ""
        else:
            label = entry.heading or ""
        lines.append(f"  {c(f'{entry.ref:<5}', GOLD_B)} {label}")
    return "\n".join(lines)


def format_proofs(entry: Entry, width: int = 88, color: bool = False) -> str:
    if not entry.proofs:
        return ""
    c = lambda t, code: _color(t, code, color)
    wrapper = textwrap.TextWrapper(width=width, initial_indent="  ", subsequent_indent="     ")
    lines = [c("Scripture Proofs", OX_B)]
    for proof in entry.proofs:
        marker = f"{proof.letter}."
        filled = wrapper.fill(f"{marker} {'; '.join(proof.references)}")
        if color:
            filled = filled.replace(marker, c(marker, GOLD_B), 1)
        lines.append(filled)
    return "\n".join(lines)


MESV_TAG = "2025 MESV (study version)"


def _entry_question(entry: Entry, mesv: bool) -> str:
    return (entry.question_mesv if mesv else entry.question) or ""


def _entry_answer(entry: Entry, mesv: bool) -> str:
    return (entry.answer_mesv if mesv else entry.answer) or ""


def _entry_heading(entry: Entry, mesv: bool) -> str:
    return (entry.heading_mesv if mesv else entry.heading) or ""


def _entry_text(entry: Entry, mesv: bool) -> str:
    return (entry.text_mesv if mesv else entry.text) or ""


def _entry_body(entry: Entry, wrapper, color: bool, mesv: bool) -> list[str]:
    c = lambda t, code: _color(t, code, color)
    lines: list[str] = []
    if entry.kind == "qa":
        lines.append("")
        q = wrapper.fill(f"Q. {_entry_question(entry, mesv)}")
        a = wrapper.fill(f"A. {_entry_answer(entry, mesv)}")
        lines.append(_prefix(q, "Q.", GOLD_B, color))
        lines.append("")
        lines.append(_prefix(a, "A.", OX_B, color))
    else:
        heading = _entry_heading(entry, mesv)
        if heading:
            lines.append(c(heading, OX))
        text = _entry_text(entry, mesv)
        if text:
            lines.append("")
            lines.append(wrapper.fill(text))
    return lines


def format_entry(
    entry: Entry,
    width: int = 88,
    color: bool = False,
    proofs: bool = False,
    mesv: bool = False,
    compare: bool = False,
) -> str:
    c = lambda t, code: _color(t, code, color)
    wrapper = textwrap.TextWrapper(width=width, subsequent_indent="    ")

    title = entry.doc_title
    if mesv and not compare:
        title += f" · {MESV_TAG}"
    header = (
        c(f"{entry.doc_id.upper()} · {entry.ref}", STRONG)
        + "   "
        + c(title, MUTE)
    )
    lines = [header, c("─" * 54, GOLD)]

    if compare:
        lines.append("")
        lines.append(c("Constitutional", OX_B))
        lines.extend(_entry_body(entry, wrapper, color, mesv=False))
        lines.append("")
        lines.append(c(MESV_TAG, OX_B))
        lines.extend(_entry_body(entry, wrapper, color, mesv=True))
    else:
        lines.extend(_entry_body(entry, wrapper, color, mesv=mesv))

    if proofs:
        block = format_proofs(entry, width=width, color=color)
        if block:
            lines.append("")
            lines.append(block)
    return "\n".join(lines)


def _prefix(text: str, prefix: str, code: str, enabled: bool) -> str:
    if not enabled or not text.startswith(prefix):
        return text
    return _color(prefix, code, enabled) + text[len(prefix):]


def format_entry_part(entry: Entry, part: str, mesv: bool = False) -> str:
    if part == "question":
        return _entry_question(entry, mesv)
    if part == "answer":
        return _entry_answer(entry, mesv)
    raise ValueError(f"Unsupported entry part: {part}")


def format_chapter(
    document: Document,
    chapter: str,
    entries: list[Entry],
    width: int = 88,
    color: bool = False,
    proofs: bool = False,
    mesv: bool = False,
    compare: bool = False,
) -> str:
    c = lambda t, code: _color(t, code, color)
    wrapper = textwrap.TextWrapper(width=width, subsequent_indent="    ")
    heading = _entry_heading(entries[0], mesv and not compare) if entries else None

    title = document.title
    if mesv and not compare:
        title += f" · {MESV_TAG}"
    lines = [
        c(f"{document.id.upper()} · Chapter {chapter}", STRONG) + "   " + c(title, MUTE),
        c("─" * 60, GOLD),
    ]
    if heading:
        lines.append(c(heading, OX))

    for entry in entries:
        lines.append("")
        lines.append(c(entry.ref, GOLD_B))
        if compare:
            lines.append(c("Constitutional", OX_B))
            text = _entry_text(entry, mesv=False)
            if text:
                lines.append(wrapper.fill(text))
            lines.append(c(MESV_TAG, OX_B))
            text = _entry_text(entry, mesv=True)
            if text:
                lines.append(wrapper.fill(text))
        else:
            text = _entry_text(entry, mesv)
            if text:
                lines.append(wrapper.fill(text))
        if proofs:
            block = format_proofs(entry, width=width, color=color)
            if block:
                lines.append(block)

    return "\n".join(lines)


def format_sources(documents: tuple[Document, ...]) -> str:
    lines = ["Sources:"]
    for document in documents:
        lines.append(f"  {document.id:<4} {document.source} - {document.source_url}")
    return "\n".join(lines)


def format_search_results(entries: list[Entry], color: bool = False) -> str:
    if not entries:
        return "No matches found."

    c = lambda t, code: _color(t, code, color)
    count = len(entries)
    plural = "match" if count == 1 else "matches"
    lines = [
        c(f"{count} {plural}", STRONG),
        c("─" * 54, GOLD),
    ]
    for entry in entries:
        if entry.kind == "qa":
            preview = entry.question or entry.answer or ""
        else:
            preview = entry.heading or entry.text or ""
        lines.append(f"  {c(f'{entry.label:<9}', GOLD_B)} {preview}")
    return "\n".join(lines)


def format_quiz_summary(correct: int, total: int, color: bool = False) -> str:
    c = lambda t, code: _color(t, code, color)
    return c("Score", OX_B) + "  " + c(f"{correct} / {total}", GOLD)
