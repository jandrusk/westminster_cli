import contextlib
import io
import asyncio
import unittest
from unittest import mock

from prompt_toolkit.document import Document

from westminster_cli.cli import (
    WestminsterCompleter,
    _accept_completion_or_submit,
    _normalize_slash_args,
    _page,
    dispatch,
    load_documents,
    main,
    run_quiz,
    run_repl,
)
from westminster_cli.formatting import format_entry


def _prompt_text(message):
    """Render a prompt_toolkit prompt message (str or list of (style, text)) to plain text."""
    if isinstance(message, str):
        return message
    return "".join(fragment[1] for fragment in message)


class CliTests(unittest.TestCase):
    def run_cli(self, args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                exit_code = main(args)
            except SystemExit as exc:
                exit_code = exc.code
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def test_list_documents(self):
        exit_code, output, _ = self.run_cli(["list"])
        self.assertEqual(exit_code, 0)
        self.assertIn("wsc", output)
        self.assertIn("Westminster Shorter Catechism", output)
        self.assertIn("dpw", output)
        self.assertIn("Directory for the Public Worship of God", output)

    def test_no_args_shows_terminal_home(self):
        documents = load_documents()
        stdout = io.StringIO()
        with mock.patch(
            "westminster_cli.cli._build_prompt_session",
            return_value=None,
        ), mock.patch("builtins.input", side_effect=["exit"]), contextlib.redirect_stdout(stdout):
            exit_code = run_repl(documents)
        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("W  E  S  T  M  I  N  S  T  E  R", output)
        self.assertIn("S T A N D A R D S", output)
        self.assertIn("ws wcf 1.1", output)
        self.assertIn("ws /", output)
        self.assertIn("Interactive mode", output)

    def test_interactive_loop_runs_commands_until_exit(self):
        documents = load_documents()
        stdout = io.StringIO()
        with mock.patch(
            "westminster_cli.cli._build_prompt_session",
            return_value=None,
        ), mock.patch(
            "builtins.input",
            side_effect=["/", "wsc 1 --question", "exit"],
        ), contextlib.redirect_stdout(stdout):
            exit_code = run_repl(documents)
        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("SLASH COMMANDS", output)
        self.assertIn("What is the chief end of man?", output)

    def test_interactive_loop_continues_after_invalid_input(self):
        documents = load_documents()
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch(
            "westminster_cli.cli._build_prompt_session",
            return_value=None,
        ), mock.patch(
            "builtins.input",
            side_effect=["unknown", "exit"],
        ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = run_repl(documents)
        self.assertEqual(exit_code, 0)
        self.assertIn("invalid choice", stderr.getvalue())

    def test_interactive_loop_clear_continues(self):
        documents = load_documents()
        stdout = io.StringIO()
        with mock.patch(
            "westminster_cli.cli._build_prompt_session",
            return_value=None,
        ), mock.patch(
            "builtins.input",
            side_effect=["clear", "wsc 1 --question", "exit"],
        ), contextlib.redirect_stdout(stdout):
            exit_code = run_repl(documents)
        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("\033[2J\033[H", output)
        self.assertIn("What is the chief end of man?", output)

    def test_prompt_toolkit_loop_uses_prompt_session(self):
        class FakePromptSession:
            def __init__(self):
                self.lines = iter(["/q wsc 1", "exit"])

            def prompt(self, message):
                self.prompt_message = message
                return next(self.lines)

        documents = load_documents()
        fake_session = FakePromptSession()
        stdout = io.StringIO()
        with mock.patch(
            "westminster_cli.cli._build_prompt_session",
            return_value=fake_session,
        ), contextlib.redirect_stdout(stdout):
            exit_code = run_repl(documents)
        self.assertEqual(exit_code, 0)
        self.assertEqual(_prompt_text(fake_session.prompt_message), "ws> ")
        self.assertIn("What is the chief end of man?", stdout.getvalue())

    def completions_for(self, text):
        return list(WestminsterCompleter().get_completions(Document(text), None))

    def document_completions_for(self, text):
        return list(
            WestminsterCompleter(load_documents()).get_completions(Document(text), None)
        )

    async def async_completions_for(self, text):
        completions = []
        async for completion in WestminsterCompleter().get_completions_async(Document(text), None):
            completions.append(completion)
        return completions

    def test_intellitype_slash_lists_slash_commands(self):
        completions = self.completions_for("/")
        texts = [completion.text for completion in completions]
        self.assertIn("/wcf ", texts)
        self.assertIn("/wsc ", texts)
        self.assertIn("/q wsc ", texts)
        self.assertIn("/stats", texts)

    def test_intellitype_slash_filters_document_commands(self):
        completions = self.completions_for("/w")
        texts = [completion.text for completion in completions]
        self.assertEqual(texts, ["/wcf ", "/wsc ", "/wlc "])

    def test_intellitype_plain_filters_system_commands(self):
        completions = self.completions_for("s")
        texts = [completion.text for completion in completions]
        self.assertEqual(texts, ["search ", "stats", "sources"])

    def test_intellitype_clear_completion(self):
        completions = self.completions_for("cl")
        texts = [completion.text for completion in completions]
        self.assertEqual(texts, ["clear"])
        self.assertEqual(completions[0].display_meta_text, "Clear the terminal")

    def test_intellitype_completion_metadata_describes_command(self):
        completions = self.completions_for("/q")
        self.assertEqual(completions[0].text, "/q wsc ")
        self.assertEqual(completions[0].display_meta_text, "Print only a catechism question")

    def test_intellitype_argument_templates_keep_trailing_space(self):
        completions = self.completions_for("wcf")
        self.assertEqual(completions[0].text, "wcf ")

    def test_intellitype_slash_aliases_suggest_references(self):
        cases = {
            "/q wsc ": "107",
            "/a wlc ": "196",
            "/p wcf ": "33.3",
            "/m wsc ": "107",
        }
        for prompt, expected_ref in cases.items():
            with self.subTest(prompt=prompt):
                completions = self.document_completions_for(prompt)
                self.assertIn(expected_ref, [completion.text for completion in completions])

    def test_intellitype_slash_aliases_suggest_document_ids(self):
        completions = self.document_completions_for("/q ")
        self.assertEqual([completion.text for completion in completions], ["wsc", "wlc"])

    def test_intellitype_async_completions_match_prompt_toolkit_contract(self):
        completions = asyncio.run(self.async_completions_for("/w"))
        texts = [completion.text for completion in completions]
        self.assertEqual(texts, ["/wcf ", "/wsc ", "/wlc "])

    def test_accepting_argument_template_keeps_prompt_open(self):
        completion = self.completions_for("/w")[0]
        buffer = mock.Mock()
        buffer.complete_state.current_completion = completion

        _accept_completion_or_submit(buffer)

        buffer.apply_completion.assert_called_once_with(completion)
        buffer.start_completion.assert_called_once_with(select_first=False)
        buffer.validate_and_handle.assert_not_called()

    def test_accepting_complete_command_submits_prompt(self):
        completion = self.completions_for("sta")[0]
        buffer = mock.Mock()
        buffer.complete_state.current_completion = completion

        _accept_completion_or_submit(buffer)

        buffer.apply_completion.assert_called_once_with(completion)
        buffer.start_completion.assert_not_called()
        buffer.validate_and_handle.assert_called_once_with()

    def test_slash_shows_command_menu(self):
        exit_code, output, _ = self.run_cli(["/"])
        self.assertEqual(exit_code, 0)
        self.assertIn("SLASH COMMANDS", output)
        self.assertIn("/wcf 1", output)
        self.assertIn("/q wsc 1", output)

    def test_slash_help_shows_command_menu(self):
        exit_code, output, _ = self.run_cli(["/help"])
        self.assertEqual(exit_code, 0)
        self.assertIn("SLASH COMMANDS", output)
        self.assertIn("/stats", output)

    def test_clear_command_clears_terminal(self):
        exit_code, output, _ = self.run_cli(["clear"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(output, "\033[2J\033[H")

    def test_slash_clear_command_clears_terminal(self):
        exit_code, output, _ = self.run_cli(["/clear"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(output, "\033[2J\033[H")

    def test_show_shorter_catechism_question(self):
        exit_code, output, _ = self.run_cli(["show", "wsc", "1"])
        self.assertEqual(exit_code, 0)
        self.assertIn("chief end of man", output)
        self.assertIn("glorify God", output)

    def test_show_wcf_chapter(self):
        exit_code, output, _ = self.run_cli(["show", "wcf", "1"])
        self.assertEqual(exit_code, 0)
        self.assertIn("WCF · Chapter 1", output)
        self.assertIn("Westminster Confession of Faith", output)
        self.assertIn("Of the Holy Scripture", output)
        self.assertIn("1.1", output)
        self.assertIn("1.10", output)

    def test_show_wcf_chapter_does_not_match_other_chapters(self):
        exit_code, output, _ = self.run_cli(["show", "wcf", "1"])
        self.assertEqual(exit_code, 0)
        self.assertNotIn("Of Effectual Calling", output)

    def test_show_wcf_section_still_uses_exact_reference(self):
        exit_code, output, _ = self.run_cli(["show", "wcf", "1.1"])
        self.assertEqual(exit_code, 0)
        self.assertIn("WCF · 1.1", output)
        self.assertIn("Westminster Confession of Faith", output)
        self.assertNotIn("WCF · Chapter 1", output)
        self.assertNotIn("1.10", output)

    def test_shorthand_shows_wcf_chapter(self):
        exit_code, output, _ = self.run_cli(["wcf", "1"])
        self.assertEqual(exit_code, 0)
        self.assertIn("WCF · Chapter 1", output)
        self.assertIn("Westminster Confession of Faith", output)
        self.assertIn("1.10", output)

    def test_slash_shows_wcf_chapter(self):
        exit_code, output, _ = self.run_cli(["/wcf", "1"])
        self.assertEqual(exit_code, 0)
        self.assertIn("WCF · Chapter 1", output)
        self.assertIn("Westminster Confession of Faith", output)
        self.assertIn("1.10", output)

    def test_shorthand_shows_wcf_section(self):
        exit_code, output, _ = self.run_cli(["wcf", "1.1"])
        self.assertEqual(exit_code, 0)
        self.assertIn("WCF · 1.1", output)
        self.assertIn("Westminster Confession of Faith", output)
        self.assertNotIn("WCF · Chapter 1", output)

    def test_shorthand_shows_shorter_catechism_question(self):
        exit_code, output, _ = self.run_cli(["wsc", "1"])
        self.assertEqual(exit_code, 0)
        self.assertIn("WSC · 1", output)
        self.assertIn("Westminster Shorter Catechism", output)
        self.assertIn("chief end of man", output)

    def test_shorthand_shows_larger_catechism_question(self):
        exit_code, output, _ = self.run_cli(["wlc", "1"])
        self.assertEqual(exit_code, 0)
        self.assertIn("WLC · 1", output)
        self.assertIn("Westminster Larger Catechism", output)
        self.assertIn("chief and highest end of man", output)

    def test_shorthand_can_show_only_shorter_catechism_question(self):
        exit_code, output, _ = self.run_cli(["wsc", "1", "--question"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(output.strip(), "What is the chief end of man?")

    def test_slash_can_show_only_shorter_catechism_question(self):
        exit_code, output, _ = self.run_cli(["/wsc", "1", "--question"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(output.strip(), "What is the chief end of man?")

    def test_slash_question_alias(self):
        exit_code, output, _ = self.run_cli(["/q", "wsc", "1"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(output.strip(), "What is the chief end of man?")

    def test_shorthand_can_show_only_shorter_catechism_answer(self):
        exit_code, output, _ = self.run_cli(["wsc", "1", "--answer"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            output.strip(),
            "Man's chief end is to glorify God, and to enjoy him forever.",
        )

    def test_explicit_show_can_show_only_larger_catechism_answer(self):
        exit_code, output, _ = self.run_cli(["show", "wlc", "1", "-a"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            output.strip(),
            "Man's chief and highest end is to glorify God, and fully to enjoy him forever.",
        )

    def test_slash_answer_alias(self):
        exit_code, output, _ = self.run_cli(["/a", "wlc", "1"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            output.strip(),
            "Man's chief and highest end is to glorify God, and fully to enjoy him forever.",
        )

    def test_proofs_flag_shows_proofs_for_catechism_entry(self):
        exit_code, output, _ = self.run_cli(["wsc", "1", "-p"])
        self.assertEqual(exit_code, 0)
        self.assertIn("chief end of man", output)
        self.assertIn("Scripture Proofs", output)
        self.assertIn("Ps. 86:9", output)

    def test_proofs_flag_shows_proofs_for_wcf_section(self):
        exit_code, output, _ = self.run_cli(["wcf", "1.1", "--proofs"])
        self.assertEqual(exit_code, 0)
        self.assertIn("Scripture Proofs", output)
        self.assertIn("Rom. 2:14-15", output)

    def test_proofs_flag_shows_proofs_in_chapter_view(self):
        exit_code, output, _ = self.run_cli(["wcf", "1", "-p"])
        self.assertEqual(exit_code, 0)
        self.assertIn("1.10", output)
        self.assertIn("Scripture Proofs", output)
        self.assertIn("Rom. 2:14-15", output)

    def test_proofs_flag_combines_with_answer_part(self):
        exit_code, output, _ = self.run_cli(["wsc", "1", "-a", "-p"])
        self.assertEqual(exit_code, 0)
        self.assertIn("glorify God", output)
        self.assertIn("Scripture Proofs", output)
        self.assertIn("Ps. 86:9", output)

    def test_default_output_omits_proofs(self):
        exit_code, output, _ = self.run_cli(["wsc", "1"])
        self.assertEqual(exit_code, 0)
        self.assertNotIn("Scripture Proofs", output)

    def test_slash_proofs_alias(self):
        exit_code, output, _ = self.run_cli(["/p", "wsc", "1"])
        self.assertEqual(exit_code, 0)
        self.assertIn("Scripture Proofs", output)
        self.assertIn("Ps. 86:9", output)

    def test_mesv_flag_shows_modern_catechism_entry(self):
        exit_code, output, _ = self.run_cli(["wsc", "1", "-m"])
        self.assertEqual(exit_code, 0)
        self.assertIn("2025 MESV (study version)", output)
        self.assertIn("chief end of man", output)

    def test_mesv_flag_shows_modern_wcf_section(self):
        exit_code, output, _ = self.run_cli(["wcf", "1.1", "--mesv"])
        self.assertEqual(exit_code, 0)
        self.assertIn("2025 MESV (study version)", output)
        # constitutional "unexcusable" was modernized to "without excuse"
        self.assertIn("without excuse", output)
        self.assertNotIn("unexcusable", output)

    def test_mesv_flag_shows_modern_chapter_view(self):
        exit_code, output, _ = self.run_cli(["wcf", "1", "-m"])
        self.assertEqual(exit_code, 0)
        self.assertIn("1.10", output)
        self.assertIn("2025 MESV (study version)", output)

    def test_compare_shows_both_versions(self):
        exit_code, output, _ = self.run_cli(["wsc", "1", "--compare"])
        self.assertEqual(exit_code, 0)
        self.assertIn("Constitutional", output)
        self.assertIn("2025 MESV (study version)", output)

    def test_mesv_combines_with_question_part(self):
        exit_code, output, _ = self.run_cli(["wsc", "1", "-q", "-m"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(output.strip(), "What is the chief end of man?")

    def test_mesv_and_compare_are_mutually_exclusive(self):
        exit_code, _, err = self.run_cli(["wsc", "1", "-m", "--compare"])
        self.assertEqual(exit_code, 2)
        self.assertIn("not allowed", err)

    def test_slash_mesv_alias(self):
        exit_code, output, _ = self.run_cli(["/m", "wsc", "1"])
        self.assertEqual(exit_code, 0)
        self.assertIn("2025 MESV (study version)", output)

    def test_default_output_omits_mesv(self):
        exit_code, output, _ = self.run_cli(["wsc", "1"])
        self.assertEqual(exit_code, 0)
        self.assertNotIn("MESV", output)

    def test_question_answer_flags_reject_wcf_sections(self):
        exit_code, _, err = self.run_cli(["wcf", "1.1", "--question"])
        self.assertEqual(exit_code, 1)
        self.assertIn("only valid for catechism entries", err)

    def test_question_answer_flags_reject_wcf_chapters(self):
        exit_code, _, err = self.run_cli(["wcf", "1", "--answer"])
        self.assertEqual(exit_code, 1)
        self.assertIn("only valid for catechism entries", err)

    def test_search_matches_all_terms(self):
        exit_code, output, _ = self.run_cli(["search", "chief", "end"])
        self.assertEqual(exit_code, 0)
        self.assertIn("WSC 1", output)
        self.assertIn("WLC 1", output)

    def test_search_regex_flag_matches_pattern(self):
        exit_code, output, _ = self.run_cli(
            ["search", "--regex", r"chief( and highest)? end"]
        )
        self.assertEqual(exit_code, 0)
        self.assertIn("WSC 1", output)
        self.assertIn("WLC 1", output)

    def test_search_regex_short_flag(self):
        exit_code, output, _ = self.run_cli(["search", "-r", "bapti[sz]"])
        self.assertEqual(exit_code, 0)
        self.assertIn("matches", output)

    def test_search_regex_invalid_pattern_errors(self):
        exit_code, _, err = self.run_cli(["search", "--regex", "["])
        self.assertEqual(exit_code, 1)
        self.assertIn("Invalid regex", err)

    def test_search_argument_completion_suggests_regex_and_doc(self):
        documents = load_documents()
        completer = WestminsterCompleter(documents)
        texts = [c.text for c in completer.get_completions(Document("search "), None)]
        self.assertEqual(texts, ["--regex", "--doc"])

    def test_search_doc_completion_suggests_document_ids(self):
        documents = load_documents()
        completer = WestminsterCompleter(documents)
        texts = [
            c.text for c in completer.get_completions(Document("search --doc "), None)
        ]
        self.assertEqual(texts, ["wcf", "wsc", "wlc", "dpw"])

    def test_search_doc_flag_limits_to_dpw(self):
        exit_code, output, _ = self.run_cli(["search", "--doc", "dpw", "baptism"])
        self.assertEqual(exit_code, 0)
        self.assertIn("DPW", output)
        self.assertNotIn("WSC", output)
        self.assertNotIn("WCF", output)

    def test_search_doc_unknown_document_errors(self):
        exit_code, _, err = self.run_cli(["search", "--doc", "nope", "worship"])
        self.assertEqual(exit_code, 1)
        self.assertIn("Unknown document: nope", err)

    def test_show_dpw_section(self):
        exit_code, output, _ = self.run_cli(["dpw", "1.A.1"])
        self.assertEqual(exit_code, 0)
        self.assertIn("DPW · 1.A.1", output)
        self.assertIn("Directory for the Public Worship of God", output)
        self.assertIn("triune Creator", output)

    def test_show_dpw_chapter(self):
        exit_code, output, _ = self.run_cli(["dpw", "1"])
        self.assertEqual(exit_code, 0)
        self.assertIn("DPW · Chapter 1", output)
        self.assertIn("1.A.1", output)
        self.assertIn("triune Creator", output)

    def test_show_dpw_preface(self):
        exit_code, output, _ = self.run_cli(["dpw", "preface"])
        self.assertEqual(exit_code, 0)
        self.assertIn("Preface", output)
        self.assertIn("common understanding", output)

    def test_slash_stats(self):
        exit_code, output, _ = self.run_cli(["/stats"])
        self.assertEqual(exit_code, 0)
        self.assertIn("Documents: 4", output)

    def test_unknown_reference_returns_error(self):
        exit_code, _, err = self.run_cli(["show", "wsc", "999"])
        self.assertEqual(exit_code, 1)
        self.assertIn("Unknown reference", err)

    def test_unknown_wcf_chapter_returns_error(self):
        exit_code, _, err = self.run_cli(["show", "wcf", "999"])
        self.assertEqual(exit_code, 1)
        self.assertIn("Unknown reference for wcf: 999", err)

    def test_shorthand_missing_reference_remains_invalid(self):
        exit_code, _, err = self.run_cli(["wcf"])
        self.assertEqual(exit_code, 2)
        self.assertIn("required", err)

    def test_list_unknown_document_errors(self):
        exit_code, _, err = self.run_cli(["list", "wat"])
        self.assertEqual(exit_code, 1)
        self.assertIn("Unknown document: wat", err)

    def test_unknown_slash_command_falls_through_to_argparse(self):
        exit_code, _, err = self.run_cli(["/bogus"])
        self.assertEqual(exit_code, 2)
        self.assertIn("invalid choice", err)

    def test_normalize_slash_args_handles_empty_argv(self):
        self.assertEqual(_normalize_slash_args([]), [])

    def test_page_uses_less_with_color_support(self):
        with mock.patch("westminster_cli.cli.shutil.which", return_value="/usr/bin/less"), \
                mock.patch("westminster_cli.cli.subprocess.run") as run:
            _page("colored \033[1mtext\033[0m")
        args, kwargs = run.call_args
        self.assertIn("-RFX", args[0])
        self.assertEqual(kwargs["input"], b"colored \033[1mtext\033[0m")

    def test_page_strips_ansi_for_pydoc_fallback(self):
        with mock.patch("westminster_cli.cli.shutil.which", return_value=None), \
                mock.patch("westminster_cli.cli.pydoc.pager") as pager:
            _page("colored \033[1mtext\033[0m")
        pager.assert_called_once_with("colored text")

    def test_quiz_tracks_score_over_reveal_and_verdict(self):
        documents = load_documents()
        answers = iter(["", "y", "", "n"])
        outputs = []
        exit_code = run_quiz(
            documents,
            "wsc",
            2,
            read_line=lambda _prompt: next(answers),
            out=outputs.append,
        )
        text = "\n".join(outputs)
        self.assertEqual(exit_code, 0)
        self.assertIn("Score  1 / 2", text)

    def test_quiz_skip_does_not_count(self):
        documents = load_documents()
        answers = iter(["s", "", "y"])
        outputs = []
        run_quiz(
            documents,
            "wsc",
            2,
            read_line=lambda _prompt: next(answers),
            out=outputs.append,
        )
        self.assertIn("Score  1 / 1", "\n".join(outputs))

    def test_quiz_quit_stops_early(self):
        documents = load_documents()
        outputs = []
        run_quiz(
            documents,
            "wsc",
            5,
            read_line=lambda _prompt: "q",
            out=outputs.append,
        )
        self.assertIn("Score  0 / 0", "\n".join(outputs))

    def test_quiz_count_clamps_to_question_pool(self):
        documents = load_documents()
        wsc = next(document for document in documents if document.id == "wsc")
        pool_size = sum(1 for entry in wsc.entries if entry.kind == "qa")
        outputs = []
        exit_code = run_quiz(
            documents,
            "wsc",
            pool_size + 50,
            read_line=lambda _prompt: "q",
            out=outputs.append,
        )
        self.assertEqual(exit_code, 0)
        self.assertIn(f"{pool_size} questions", outputs[0])

    def test_quiz_unknown_document_errors(self):
        documents = load_documents()
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            exit_code = run_quiz(documents, "nope", 3, read_line=lambda _prompt: "")
        self.assertEqual(exit_code, 1)
        self.assertIn("Unknown document: nope", stderr.getvalue())

    def test_quiz_document_without_questions_errors(self):
        documents = load_documents()
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            exit_code = run_quiz(documents, "wcf", 3, read_line=lambda _prompt: "")
        self.assertEqual(exit_code, 1)
        self.assertIn("does not contain quiz questions", stderr.getvalue())

    def test_quiz_command_accepts_positional_doc_and_count(self):
        documents = load_documents()
        answers = iter(["", "y", "", "n"])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = dispatch(
                documents, ["quiz", "wsc", "2"], read_line=lambda _prompt: next(answers)
            )
        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Quizzing Westminster Shorter Catechism - 2 questions", output)
        self.assertIn("Score  1 / 2", output)

    def test_quiz_command_defaults_to_wsc_and_ten_questions(self):
        documents = load_documents()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = dispatch(documents, ["quiz"], read_line=lambda _prompt: "q")
        self.assertEqual(exit_code, 0)
        self.assertIn(
            "Quizzing Westminster Shorter Catechism - 10 questions", stdout.getvalue()
        )

    def test_quiz_command_rejects_count_below_one(self):
        exit_code, _, err = self.run_cli(["quiz", "wsc", "0"])
        self.assertEqual(exit_code, 1)
        self.assertIn("count must be at least 1", err)

    def test_quiz_command_unknown_document_errors(self):
        exit_code, _, err = self.run_cli(["quiz", "nope"])
        self.assertEqual(exit_code, 1)
        self.assertIn("Unknown document: nope", err)

    def test_drill_command_no_longer_exists(self):
        exit_code, _, err = self.run_cli(["drill"])
        self.assertEqual(exit_code, 2)
        self.assertIn("invalid choice", err)

    def test_completer_completes_references_after_document(self):
        documents = load_documents()
        completer = WestminsterCompleter(documents)
        texts = [c.text for c in completer.get_completions(Document("wsc 1"), None)]
        self.assertIn("1", texts)
        self.assertIn("10", texts)

    def test_completer_completes_flags_after_catechism_reference(self):
        documents = load_documents()
        completer = WestminsterCompleter(documents)
        texts = [c.text for c in completer.get_completions(Document("wsc 1 "), None)]
        self.assertEqual(
            sorted(texts),
            ["--answer", "--compare", "--mesv", "--proofs", "--question"],
        )

    def test_completer_completes_doc_ids_after_list(self):
        documents = load_documents()
        completer = WestminsterCompleter(documents)
        texts = [c.text for c in completer.get_completions(Document("list "), None)]
        self.assertEqual(texts, ["wcf", "wsc", "wlc", "dpw"])

    def test_completer_completes_dpw_references(self):
        documents = load_documents()
        completer = WestminsterCompleter(documents)
        texts = [c.text for c in completer.get_completions(Document("dpw "), None)]
        self.assertIn("preface", texts)
        self.assertIn("1.A.1", texts)

    def test_completer_without_documents_ignores_arguments(self):
        completer = WestminsterCompleter()
        texts = [c.text for c in completer.get_completions(Document("wsc 1"), None)]
        self.assertEqual(texts, [])

    def test_format_entry_color_adds_ansi(self):
        documents = load_documents()
        entry = documents[2].entries[0]
        self.assertIn("\033[", format_entry(entry, color=True))
        self.assertNotIn("\033[", format_entry(entry, color=False))

    def test_slash_quiz_alias_available(self):
        completions = self.completions_for("/quiz")
        self.assertEqual(completions[0].text, "/quiz ")

    def test_drill_command_completion_removed(self):
        self.assertEqual(self.completions_for("dri"), [])

    def test_quiz_argument_completion_suggests_catechism_documents(self):
        documents = load_documents()
        completer = WestminsterCompleter(documents)
        texts = [c.text for c in completer.get_completions(Document("quiz "), None)]
        self.assertIn("wsc", texts)
        self.assertIn("wlc", texts)
        self.assertNotIn("wcf", texts)
        self.assertNotIn("--doc", texts)

    def test_quiz_argument_completion_suggests_counts_after_document(self):
        documents = load_documents()
        completer = WestminsterCompleter(documents)
        texts = [c.text for c in completer.get_completions(Document("quiz wsc "), None)]
        self.assertEqual(texts, ["5", "10", "20"])


if __name__ == "__main__":
    unittest.main()
