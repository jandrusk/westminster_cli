import unittest

from westminster_cli.corpus import Document, Entry, Proof
from westminster_cli.formatting import (
    format_chapter,
    format_document_list,
    format_entry,
    format_entry_list,
    format_entry_part,
    format_home,
    format_proofs,
    format_quiz_summary,
    format_search_results,
    format_slash_commands,
    format_sources,
)


def _section(ref: str, heading: str = "", text: str = "") -> Entry:
    return Entry(
        doc_id="wcf",
        doc_title="Westminster Confession of Faith",
        ref=ref,
        kind="section",
        heading=heading,
        text=text,
    )


def _qa(ref: str, question: str, answer: str) -> Entry:
    return Entry(
        doc_id="wsc",
        doc_title="Westminster Shorter Catechism",
        ref=ref,
        kind="qa",
        question=question,
        answer=answer,
    )


def _document(doc_id: str, title: str, entries: tuple[Entry, ...]) -> Document:
    return Document(
        id=doc_id,
        title=title,
        short_title=title,
        source="OPC",
        source_url="https://example.com/doc",
        entries=entries,
    )


WCF = _document(
    "wcf",
    "Westminster Confession of Faith",
    (
        _section("1.1", heading="Of the Holy Scripture", text="The light of nature."),
        _section("1.2", text="The Word of God written."),
    ),
)
WSC = _document(
    "wsc",
    "Westminster Shorter Catechism",
    (_qa("1", "What is the chief end of man?", "To glorify God."),),
)

PROOFS = (
    Proof(letter="a", references=("Ps. 86:9", "Rom. 11:36")),
    Proof(letter="b", references=("Ps. 16:5-11",)),
)
QA_WITH_PROOFS = Entry(
    doc_id="wsc",
    doc_title="Westminster Shorter Catechism",
    ref="1",
    kind="qa",
    question="What is the chief end of man?",
    answer="To glorify God.",
    proofs=PROOFS,
)
SECTION_WITH_PROOFS = Entry(
    doc_id="wcf",
    doc_title="Westminster Confession of Faith",
    ref="1.1",
    kind="section",
    heading="Of the Holy Scripture",
    text="The light of nature.",
    proofs=PROOFS,
)

QA_WITH_MESV = Entry(
    doc_id="wsc",
    doc_title="Westminster Shorter Catechism",
    ref="1",
    kind="qa",
    question="What is the chief end of man?",
    answer="Man's chief end is to glorify God.",
    question_mesv="What is humanity's highest purpose?",
    answer_mesv="Our highest purpose is to glorify God.",
)
SECTION_WITH_MESV = Entry(
    doc_id="wcf",
    doc_title="Westminster Confession of Faith",
    ref="1.1",
    kind="section",
    heading="Of the Holy Scripture",
    text="The light of nature.",
    heading_mesv="Of Holy Scripture",
    text_mesv="The light of nature (modern).",
)


class FormattingTests(unittest.TestCase):
    def test_format_chapter_with_entries(self):
        output = format_chapter(WCF, "1", list(WCF.entries))
        self.assertIn("WCF · Chapter 1", output)
        self.assertIn("Of the Holy Scripture", output)
        self.assertIn("1.1", output)
        self.assertIn("1.2", output)

    def test_format_chapter_with_no_entries(self):
        output = format_chapter(WCF, "9", [])
        self.assertIn("WCF · Chapter 9", output)
        self.assertNotIn("Of the Holy Scripture", output)

    def test_format_search_results_empty(self):
        self.assertEqual(format_search_results([]), "No matches found.")

    def test_format_search_results_singular(self):
        output = format_search_results([WSC.entries[0]])
        self.assertIn("1 match", output)
        self.assertNotIn("matches", output)
        self.assertIn("What is the chief end of man?", output)

    def test_format_search_results_plural(self):
        output = format_search_results(list(WCF.entries))
        self.assertIn("2 matches", output)
        self.assertIn("Of the Holy Scripture", output)

    def test_format_document_list(self):
        output = format_document_list((WCF, WSC))
        self.assertIn("wcf", output)
        self.assertIn("Westminster Confession of Faith (2 entries)", output)
        self.assertIn("Westminster Shorter Catechism (1 entries)", output)

    def test_format_sources(self):
        output = format_sources((WCF,))
        self.assertIn("wcf", output)
        self.assertIn("OPC", output)
        self.assertIn("https://example.com/doc", output)

    def test_format_entry_list(self):
        output = format_entry_list(WSC)
        self.assertIn("Westminster Shorter Catechism", output)
        self.assertIn("What is the chief end of man?", output)

    def test_format_entry_list_uses_heading_for_sections(self):
        output = format_entry_list(WCF)
        self.assertIn("Of the Holy Scripture", output)

    def test_format_quiz_summary(self):
        self.assertIn("Score  3 / 5", format_quiz_summary(3, 5))

    def test_format_entry_part_question_and_answer(self):
        entry = WSC.entries[0]
        self.assertEqual(format_entry_part(entry, "question"), "What is the chief end of man?")
        self.assertEqual(format_entry_part(entry, "answer"), "To glorify God.")

    def test_format_entry_part_rejects_unknown_part(self):
        with self.assertRaises(ValueError):
            format_entry_part(WSC.entries[0], "heading")

    def test_format_home_smoke(self):
        output = format_home((WCF, WSC))
        self.assertIn("W  E  S  T  M  I  N  S  T  E  R", output)
        self.assertIn("2 documents", output)
        self.assertIn("3 entries", output)
        self.assertIn("Directory for Public Worship", output)
        self.assertIn("ws>", output)

    def test_format_slash_commands_smoke(self):
        output = format_slash_commands()
        self.assertIn("SLASH COMMANDS", output)
        self.assertIn("/wcf 1", output)
        self.assertIn("/dpw 1.A.1", output)
        self.assertIn("/search --doc dpw", output)
        self.assertIn("/stats", output)

    def test_format_proofs_lists_letters_and_references(self):
        output = format_proofs(QA_WITH_PROOFS)
        self.assertIn("Scripture Proofs", output)
        self.assertIn("a. Ps. 86:9; Rom. 11:36", output)
        self.assertIn("b. Ps. 16:5-11", output)

    def test_format_proofs_empty_without_proofs(self):
        self.assertEqual(format_proofs(WSC.entries[0]), "")

    def test_format_entry_proofs_flag_appends_proofs(self):
        output = format_entry(QA_WITH_PROOFS, proofs=True)
        self.assertIn("A. To glorify God.", output)
        self.assertIn("Scripture Proofs", output)
        self.assertIn("a. Ps. 86:9; Rom. 11:36", output)

    def test_format_entry_omits_proofs_by_default(self):
        output = format_entry(QA_WITH_PROOFS)
        self.assertNotIn("Scripture Proofs", output)

    def test_format_chapter_proofs_flag_appends_proofs(self):
        document = _document(
            "wcf", "Westminster Confession of Faith", (SECTION_WITH_PROOFS,)
        )
        output = format_chapter(document, "1", [SECTION_WITH_PROOFS], proofs=True)
        self.assertIn("Scripture Proofs", output)
        self.assertIn("a. Ps. 86:9; Rom. 11:36", output)
        plain = format_chapter(document, "1", [SECTION_WITH_PROOFS])
        self.assertNotIn("Scripture Proofs", plain)

    def test_format_entry_mesv_renders_modern_text_with_tag(self):
        output = format_entry(QA_WITH_MESV, mesv=True)
        self.assertIn("2025 MESV (study version)", output)
        self.assertIn("What is humanity's highest purpose?", output)
        self.assertNotIn("chief end of man", output)

    def test_format_entry_default_omits_mesv(self):
        output = format_entry(QA_WITH_MESV)
        self.assertIn("chief end of man", output)
        self.assertNotIn("highest purpose", output)
        self.assertNotIn("MESV", output)

    def test_format_entry_compare_shows_both_versions(self):
        output = format_entry(QA_WITH_MESV, compare=True)
        self.assertIn("Constitutional", output)
        self.assertIn("2025 MESV (study version)", output)
        self.assertIn("chief end of man", output)
        self.assertIn("highest purpose", output)

    def test_format_entry_mesv_section_uses_mesv_heading(self):
        output = format_entry(SECTION_WITH_MESV, mesv=True)
        self.assertIn("Of Holy Scripture", output)
        self.assertIn("The light of nature (modern).", output)
        self.assertNotIn("The light of nature.", output)

    def test_format_chapter_mesv_and_compare(self):
        document = _document(
            "wcf", "Westminster Confession of Faith", (SECTION_WITH_MESV,)
        )
        modern = format_chapter(document, "1", [SECTION_WITH_MESV], mesv=True)
        self.assertIn("The light of nature (modern).", modern)
        self.assertIn("2025 MESV (study version)", modern)
        both = format_chapter(document, "1", [SECTION_WITH_MESV], compare=True)
        self.assertIn("Constitutional", both)
        self.assertIn("The light of nature.", both)
        self.assertIn("The light of nature (modern).", both)

    def test_format_entry_part_mesv(self):
        self.assertEqual(
            format_entry_part(QA_WITH_MESV, "question", mesv=True),
            "What is humanity's highest purpose?",
        )
        self.assertEqual(
            format_entry_part(QA_WITH_MESV, "answer", mesv=True),
            "Our highest purpose is to glorify God.",
        )

    def test_format_proofs_color_toggle(self):
        self.assertNotIn("\033[", format_proofs(QA_WITH_PROOFS, color=False))
        self.assertIn("\033[", format_proofs(QA_WITH_PROOFS, color=True))

    def test_color_flag_adds_ansi_codes(self):
        plain = format_search_results(list(WCF.entries), color=False)
        colored = format_search_results(list(WCF.entries), color=True)
        self.assertNotIn("\033[", plain)
        self.assertIn("\033[", colored)


if __name__ == "__main__":
    unittest.main()
