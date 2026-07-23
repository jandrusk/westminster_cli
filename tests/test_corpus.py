import unittest

from westminster_cli.corpus import (
    Document,
    Entry,
    Proof,
    find_chapter_entries,
    find_document,
    find_entry,
    load_documents,
    search_entries,
)


def _section(doc_id: str, ref: str, heading: str = "", text: str = "") -> Entry:
    return Entry(
        doc_id=doc_id,
        doc_title="Test Document",
        ref=ref,
        kind="section",
        heading=heading,
        text=text,
    )


def _qa(doc_id: str, ref: str, question: str, answer: str) -> Entry:
    return Entry(
        doc_id=doc_id,
        doc_title="Test Document",
        ref=ref,
        kind="qa",
        question=question,
        answer=answer,
    )


def _document(doc_id: str, entries: tuple[Entry, ...]) -> Document:
    return Document(
        id=doc_id,
        title="Test Document",
        short_title="Test",
        source="Test Source",
        source_url="https://example.com",
        entries=entries,
    )


class CorpusTests(unittest.TestCase):
    def setUp(self):
        self.wcf = _document(
            "wcf",
            (
                _section("wcf", "1.1", heading="Of the Holy Scripture", text="light of nature"),
                _section("wcf", "1.2", text="Holy Scripture"),
                _section("wcf", "10.1", heading="Of Effectual Calling", text="effectual calling"),
            ),
        )
        self.wsc = _document(
            "wsc",
            (
                _qa("wsc", "1", "What is the chief end of man?", "To glorify God."),
                _qa("wsc", "2", "What rule hath God given?", "The Word of God."),
            ),
        )
        self.documents = (self.wcf, self.wsc)

    def test_find_document_returns_matching_document(self):
        self.assertIs(find_document(self.documents, "wsc"), self.wsc)

    def test_find_document_is_case_insensitive(self):
        self.assertIs(find_document(self.documents, "WCF"), self.wcf)

    def test_find_document_unknown_returns_none(self):
        self.assertIsNone(find_document(self.documents, "nope"))

    def test_find_entry_returns_matching_entry(self):
        entry = find_entry(self.wcf, "1.2")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.ref, "1.2")

    def test_find_entry_is_case_insensitive(self):
        wsc_upper = _document("wsc", (_qa("wsc", "1A", "Q?", "A."),))
        entry = find_entry(wsc_upper, "1a")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.ref, "1A")

    def test_find_entry_unknown_returns_none(self):
        self.assertIsNone(find_entry(self.wcf, "999"))

    def test_find_chapter_entries_uses_dot_prefix(self):
        refs = [entry.ref for entry in find_chapter_entries(self.wcf, "1")]
        self.assertEqual(refs, ["1.1", "1.2"])
        self.assertNotIn("10.1", refs)

    def test_find_chapter_entries_unknown_chapter_returns_empty(self):
        self.assertEqual(find_chapter_entries(self.wcf, "99"), [])

    def test_search_entries_requires_all_terms(self):
        matches = search_entries(self.documents, "chief end")
        self.assertEqual([entry.ref for entry in matches], ["1"])
        self.assertEqual(search_entries(self.documents, "chief calling"), [])

    def test_search_entries_is_case_insensitive(self):
        matches = search_entries(self.documents, "GLORIFY")
        self.assertEqual([entry.ref for entry in matches], ["1"])

    def test_search_entries_empty_query_returns_empty(self):
        self.assertEqual(search_entries(self.documents, ""), [])
        self.assertEqual(search_entries(self.documents, "   "), [])

    def test_search_entries_regex_matches_pattern(self):
        matches = search_entries(self.documents, r"chief end of man\?", regex=True)
        self.assertEqual([entry.ref for entry in matches], ["1"])

    def test_search_entries_regex_alternation_spans_documents(self):
        matches = search_entries(self.documents, r"effectual|chief", regex=True)
        refs = {(entry.doc_id, entry.ref) for entry in matches}
        self.assertIn(("wcf", "10.1"), refs)
        self.assertIn(("wsc", "1"), refs)

    def test_search_entries_regex_is_case_insensitive(self):
        matches = search_entries(self.documents, r"GLORIFY\s+GOD", regex=True)
        self.assertEqual([entry.ref for entry in matches], ["1"])

    def test_search_entries_regex_invalid_pattern_raises(self):
        with self.assertRaises(ValueError) as ctx:
            search_entries(self.documents, "[", regex=True)
        self.assertIn("Invalid regex", str(ctx.exception))

    def test_entry_proofs_default_to_empty(self):
        entry = _qa("wsc", "1", "Q?", "A.")
        self.assertEqual(entry.proofs, ())

    def test_load_documents_parses_proofs(self):
        documents = load_documents()
        wsc = find_document(documents, "wsc")
        first = wsc.entries[0]
        self.assertGreater(len(first.proofs), 0)
        self.assertIsInstance(first.proofs[0], Proof)
        self.assertEqual(first.proofs[0].letter, "a")
        self.assertIn("Ps. 86:9", first.proofs[0].references)

    def test_load_documents_every_wsc_entry_has_proofs(self):
        documents = load_documents()
        wsc = find_document(documents, "wsc")
        missing = [entry.ref for entry in wsc.entries if not entry.proofs]
        self.assertEqual(missing, [])

    def test_load_documents_parses_mesv_fields(self):
        documents = load_documents()
        wsc = find_document(documents, "wsc")
        first = wsc.entries[0]
        self.assertEqual(first.question_mesv, "What is the chief end of man?")
        self.assertTrue(first.answer_mesv)
        wcf = find_document(documents, "wcf")
        section = find_entry(wcf, "1.1")
        self.assertTrue(section.text_mesv)
        self.assertEqual(section.heading_mesv, "Of the Holy Scripture")

    def test_load_documents_every_confession_catechism_entry_has_mesv_text(self):
        documents = load_documents()
        missing = [
            f"{document.id} {entry.ref}"
            for document in documents
            if document.id in {"wcf", "wlc", "wsc"}
            for entry in document.entries
            if not (entry.text_mesv or (entry.question_mesv and entry.answer_mesv))
        ]
        self.assertEqual(missing, [])

    def test_load_documents_returns_four_consistent_documents(self):
        documents = load_documents()
        self.assertEqual(len(documents), 4)
        self.assertEqual(
            {document.id for document in documents}, {"wcf", "wlc", "wsc", "dpw"}
        )
        for document in documents:
            self.assertGreater(len(document.entries), 0)
            for entry in document.entries:
                self.assertEqual(entry.doc_id, document.id)
                self.assertEqual(entry.doc_title, document.title)

    def test_load_documents_includes_directory_for_public_worship(self):
        documents = load_documents()
        dpw = find_document(documents, "dpw")
        self.assertIsNotNone(dpw)
        self.assertEqual(dpw.title, "Directory for the Public Worship of God")
        self.assertGreater(len(dpw.entries), 50)
        preface = find_entry(dpw, "preface")
        self.assertIsNotNone(preface)
        self.assertIn("common understanding", preface.text or "")
        first = find_entry(dpw, "1.A.1")
        self.assertIsNotNone(first)
        self.assertIn("triune Creator", first.text or "")

    def test_search_entries_can_find_dpw_content(self):
        documents = load_documents()
        matches = search_entries(documents, "directory public worship principles")
        self.assertTrue(any(entry.doc_id == "dpw" for entry in matches))


if __name__ == "__main__":
    unittest.main()
