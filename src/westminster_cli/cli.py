from __future__ import annotations

import argparse
import pydoc
import random
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .corpus import (
    find_chapter_entries,
    find_document,
    find_entry,
    load_documents,
    search_entries,
)
from .formatting import (
    format_chapter,
    format_document_list,
    format_entry,
    format_entry_part,
    format_entry_list,
    format_home,
    format_proofs,
    format_quiz_summary,
    format_search_results,
    format_slash_commands,
    format_sources,
)


DOCUMENT_IDS = {"wcf", "wlc", "wsc", "dpw"}
# prompt_toolkit's FileHistory and readline write incompatible formats;
# sharing one file makes each rewrite the other's entries (with re-escaping),
# growing the file without bound. Keep them strictly separate.
HISTORY_FILE = Path.home() / ".westminster_standards_history"
READLINE_HISTORY_FILE = Path.home() / ".westminster_standards_history_readline"

# Producers whose output can be long; page these when writing to a TTY.
PAGE_THRESHOLD = 20

ANSI_ESCAPE_RE = re.compile(r"\033\[[0-9;]*m")


@dataclass(frozen=True)
class CommandCompletion:
    text: str
    description: str


COMMAND_COMPLETIONS = (
    CommandCompletion("/wcf ", "Show WCF chapter or section"),
    CommandCompletion("/wsc ", "Show Shorter Catechism question"),
    CommandCompletion("/wlc ", "Show Larger Catechism question"),
    CommandCompletion("/dpw ", "Show Directory for Public Worship section"),
    CommandCompletion("/q wsc ", "Print only a catechism question"),
    CommandCompletion("/a wsc ", "Print only a catechism answer"),
    CommandCompletion("/p wsc ", "Show an entry with scripture proof texts"),
    CommandCompletion("/m wsc ", "Show an entry in modern English (2025 MESV)"),
    CommandCompletion("/search ", "Search the standards"),
    CommandCompletion("/dpw-search ", "Search the Directory for Public Worship"),
    CommandCompletion("/list ", "List documents or entries"),
    CommandCompletion("/quiz ", "Flashcard quiz (reveal answers, track score)"),
    CommandCompletion("/stats", "Show corpus counts"),
    CommandCompletion("/sources", "Show OPC source pages"),
    CommandCompletion("/clear", "Clear the terminal"),
    CommandCompletion("/help", "Show slash command menu"),
    CommandCompletion("wcf ", "Show WCF chapter or section"),
    CommandCompletion("wsc ", "Show Shorter Catechism question"),
    CommandCompletion("wlc ", "Show Larger Catechism question"),
    CommandCompletion("dpw ", "Show Directory for Public Worship section"),
    CommandCompletion("dpw-search ", "Search the Directory for Public Worship"),
    CommandCompletion("search ", "Search the standards"),
    CommandCompletion("list ", "List documents or entries"),
    CommandCompletion("quiz ", "Flashcard quiz (reveal answers, track score)"),
    CommandCompletion("stats", "Show corpus counts"),
    CommandCompletion("sources", "Show OPC source pages"),
    CommandCompletion("clear", "Clear the terminal"),
    CommandCompletion("help", "Show CLI help"),
    CommandCompletion("exit", "Exit interactive mode"),
)


class WestminsterCompleter:
    def __init__(self, documents=None):
        self.documents = documents

    def get_completions(self, document, complete_event):
        prefix = document.text_before_cursor.lstrip()
        if not prefix:
            return
        if " " not in prefix:
            yield from self._command_completions(prefix)
            return
        if self.documents is not None:
            yield from self._argument_completions(prefix)

    def _command_completions(self, prefix):
        from prompt_toolkit.completion import Completion

        start_position = -len(prefix)
        for command in COMMAND_COMPLETIONS:
            if command.text.startswith(prefix):
                yield Completion(
                    command.text,
                    start_position=start_position,
                    display=command.text.rstrip(),
                    display_meta=command.description,
                )

    def _argument_completions(self, prefix):
        from prompt_toolkit.completion import Completion

        tokens = prefix.split()
        ends_with_space = prefix.endswith(" ")
        current = "" if ends_with_space else tokens[-1]
        word_index = len(tokens) if ends_with_space else len(tokens) - 1
        start_position = -len(current)

        def emit(value, meta):
            if value.startswith(current):
                yield Completion(
                    value, start_position=start_position, display=value, display_meta=meta
                )

        first = tokens[0].lstrip("/").casefold()

        if first in {"q", "a", "p", "m"}:
            if word_index == 1:
                if first in {"q", "a"}:
                    doc_ids = ("wsc", "wlc")
                elif first in {"p", "m"}:
                    doc_ids = ("wcf", "wsc", "wlc")
                else:
                    doc_ids = tuple(DOCUMENT_IDS)
                for doc_id in doc_ids:
                    yield from emit(doc_id, "Document")
                return
            if len(tokens) < 2:
                return
            first = tokens[1].casefold()
            word_index -= 1

        if first in DOCUMENT_IDS:
            document = find_document(self.documents, first)
            if document is None:
                return
            if first == "dpw" and len(tokens) > 1 and tokens[1].casefold().startswith("search"):
                if word_index == 2 and tokens[1].casefold() == "search":
                    yield from emit("--regex", "Regular expression search")
                return
            if word_index == 1:
                if first == "dpw":
                    yield from emit("search", "Search the Directory for Public Worship")
                for entry in document.entries:
                    yield from emit(entry.ref, _entry_meta(entry))
            elif word_index == 2:
                if any(entry.kind == "qa" for entry in document.entries):
                    yield from emit("--question", "Only the question")
                    yield from emit("--answer", "Only the answer")
                if first != "dpw":
                    yield from emit("--proofs", "Show scripture proof texts")
                    yield from emit("--mesv", "Modern English Study Version")
                    yield from emit("--compare", "Constitutional and MESV together")
            return

        if first == "list" and word_index == 1:
            for doc_id in ("wcf", "wsc", "wlc", "dpw"):
                yield from emit(doc_id, "Document")
            return

        if first == "search" and word_index == 1:
            yield from emit("--regex", "Regular expression search")
            yield from emit("--doc", "Limit search to one document")
            return

        if first == "search" and word_index == 2 and tokens[1] in {"--doc", "-d"}:
            for doc_id in ("wcf", "wsc", "wlc", "dpw"):
                yield from emit(doc_id, "Document")
            return

        if first == "quiz":
            if word_index == 1:
                for doc in self.documents:
                    if any(entry.kind == "qa" for entry in doc.entries):
                        yield from emit(doc.id, doc.short_title)
            elif word_index == 2:
                for count in ("5", "10", "20"):
                    yield from emit(count, "Number of questions")

    async def get_completions_async(self, document, complete_event):
        for completion in self.get_completions(document, complete_event):
            yield completion


def _entry_meta(entry) -> str:
    text = entry.question or entry.heading or entry.text or ""
    return f"{text[:40]}…" if len(text) > 40 else text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ws",
        usage=(
            "%(prog)s [-h] {wcf,wlc,wsc,dpw} ref | "
            "{list,search,quiz,stats,sources,clear} ..."
        ),
        description="Read, search, and quiz yourself on the Westminster Standards.",
        epilog=(
            "Examples: ws wcf 1, ws wcf 1.1, ws wsc 1 --question, "
            'ws search "chief end", ws search --doc dpw baptism, '
            "ws dpw 1.A.1. The explicit form `ws show DOC REF` still works."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List documents or entries in a document.")
    list_parser.add_argument(
        "doc", nargs="?", help="Document id, such as wsc, wlc, wcf, or dpw."
    )

    search_parser = subparsers.add_parser("search", help="Search across the bundled corpus.")
    search_parser.add_argument("query", nargs="+", help="Search terms.")
    search_parser.add_argument(
        "-r",
        "--regex",
        action="store_true",
        help="Treat the query as a case-insensitive regular expression.",
    )
    search_parser.add_argument(
        "-d",
        "--doc",
        metavar="DOC",
        help="Limit search to one document (wcf, wlc, wsc, or dpw).",
    )

    quiz_parser = subparsers.add_parser(
        "quiz", help="Flashcard quiz: reveal answers and track your score."
    )
    quiz_parser.add_argument(
        "doc", nargs="?", default="wsc", help="Document id to quiz from. Defaults to wsc."
    )
    quiz_parser.add_argument(
        "count", nargs="?", type=int, default=10, help="Number of questions. Defaults to 10."
    )

    dpw_search_parser = subparsers.add_parser(
        "dpw-search", help="Search the Directory for Public Worship."
    )
    dpw_search_parser.add_argument("query", nargs="+", help="Search terms.")
    dpw_search_parser.add_argument(
        "-r",
        "--regex",
        action="store_true",
        help="Treat the query as a case-insensitive regular expression.",
    )

    subparsers.add_parser("stats", help="Show corpus counts.")
    subparsers.add_parser("sources", help="Show OPC source pages for the bundled corpus.")
    subparsers.add_parser("clear", help="Clear the terminal.")

    return parser


def build_show_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ws show",
        description="Show a catechism question, confession section, or WCF chapter.",
    )
    parser.add_argument("doc", help="Document id, such as wsc, wlc, wcf, or dpw.")
    parser.add_argument("ref", help="Entry reference, such as 1, 1.1, or 1.A.1.")
    part_group = parser.add_mutually_exclusive_group()
    part_group.add_argument(
        "-q",
        "--question",
        action="store_const",
        const="question",
        dest="part",
        help="Only print the question for a catechism entry.",
    )
    part_group.add_argument(
        "-a",
        "--answer",
        action="store_const",
        const="answer",
        dest="part",
        help="Only print the answer for a catechism entry.",
    )
    parser.add_argument(
        "-p",
        "--proofs",
        action="store_true",
        help="Show the OPC scripture proof texts beneath the text.",
    )
    version_group = parser.add_mutually_exclusive_group()
    version_group.add_argument(
        "-m",
        "--mesv",
        action="store_true",
        help="Show the 2025 Modern English Study Version text.",
    )
    version_group.add_argument(
        "--compare",
        action="store_true",
        help="Show the constitutional and 2025 MESV texts together.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    raw_args = sys.argv[1:] if argv is None else argv
    documents = load_documents()

    if not raw_args:
        return run_repl(documents)
    return dispatch(documents, raw_args)


def dispatch(documents, raw_args: list[str], read_line=input) -> int:
    slash_args = _normalize_slash_args(raw_args)
    if slash_args == []:
        print(format_slash_commands(color=sys.stdout.isatty()))
        return 0
    raw_args = slash_args

    if (
        raw_args
        and raw_args[0].casefold() in DOCUMENT_IDS
        and len(raw_args) > 1
        and raw_args[1].casefold() == "search"
    ):
        return _dpw_search(documents, raw_args[2:])
    if raw_args and raw_args[0].casefold() in DOCUMENT_IDS:
        return _show(documents, raw_args)
    if raw_args and raw_args[0] == "show":
        return _show(documents, raw_args[1:])
    if raw_args and raw_args[0] == "clear":
        _clear_screen()
        return 0
    if raw_args and raw_args[0] == "help":
        build_parser().print_help()
        return 0

    parser = build_parser()
    args = parser.parse_args(raw_args)

    if args.command == "list":
        if args.doc is None:
            print(format_document_list(documents))
            return 0
        document = find_document(documents, args.doc)
        if document is None:
            return _error(f"Unknown document: {args.doc}")
        _emit(format_entry_list(document, color=_color_enabled()), page=True)
        return 0

    if args.command == "search":
        query = " ".join(args.query)
        search_docs = documents
        if args.doc is not None:
            document = find_document(documents, args.doc)
            if document is None:
                return _error(f"Unknown document: {args.doc}")
            search_docs = (document,)
        try:
            results = search_entries(search_docs, query, regex=args.regex)
        except ValueError as exc:
            return _error(str(exc))
        _emit(format_search_results(results, color=_color_enabled()), page=True)
        return 0

    if args.command == "quiz":
        if args.count < 1:
            return _error("count must be at least 1")
        return run_quiz(documents, args.doc, args.count, read_line)

    if args.command == "dpw-search":
        return _dpw_search(documents, args.query + (["--regex"] if args.regex else []))

    if args.command == "stats":
        total = sum(len(document.entries) for document in documents)
        qa_count = sum(
            1 for document in documents for entry in document.entries if entry.kind == "qa"
        )
        print(f"Documents: {len(documents)}")
        print(f"Entries: {total}")
        print(f"Catechism questions: {qa_count}")
        return 0

    if args.command == "sources":
        print(format_sources(documents))
        return 0

    if args.command == "clear":
        _clear_screen()
        return 0

    parser.print_help()
    return 2


def run_quiz(documents, doc_id: str, count: int, read_line=input, *, out=print) -> int:
    document = find_document(documents, doc_id)
    if document is None:
        return _error(f"Unknown document: {doc_id}")
    questions = [entry for entry in document.entries if entry.kind == "qa"]
    if not questions:
        return _error(f"{document.id} does not contain quiz questions")

    sample_size = min(count, len(questions))
    selection = random.sample(questions, sample_size)
    out(f"Quizzing {document.title} - {sample_size} questions. Enter to reveal, s skip, q quit.")

    correct = 0
    answered = 0
    for index, entry in enumerate(selection, start=1):
        out("")
        out(f"{index}. {entry.label}")
        out(f"Q. {entry.question}")
        try:
            reveal = read_line("[Enter to reveal] ").strip().casefold()
        except (EOFError, KeyboardInterrupt):
            out("")
            break
        if reveal in {"q", "quit", "exit"}:
            break
        if reveal in {"s", "skip"}:
            continue
        out(f"A. {entry.answer}")
        try:
            verdict = read_line("Got it? [y/n] ").strip().casefold()
        except (EOFError, KeyboardInterrupt):
            out("")
            break
        answered += 1
        if verdict in {"y", "yes"}:
            correct += 1

    out("")
    out(format_quiz_summary(correct, answered, color=_color_enabled()))
    return 0


def run_repl(documents=None) -> int:
    if documents is None:
        documents = load_documents()
    print(format_home(documents, color=sys.stdout.isatty()))
    print()
    print("Interactive mode. Type / for commands, help for help, or exit to quit.")

    prompt_session = _build_prompt_session(documents)
    if prompt_session is not None:
        return _run_prompt_toolkit_repl(documents, prompt_session)

    return _run_input_repl(documents)


def _run_prompt_toolkit_repl(documents, prompt_session) -> int:
    read_line = _plain_prompt(prompt_session)
    while True:
        try:
            line = prompt_session.prompt([("class:prompt", "ws> ")])
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if _dispatch_repl_line(documents, line, read_line):
            return 0


def _run_input_repl(documents) -> int:
    _enable_history()

    while True:
        try:
            line = input("ws> ")
        except EOFError:
            print()
            return 0
        if _dispatch_repl_line(documents, line, input):
            return 0


def _plain_prompt(prompt_session):
    """A read_line callable that uses the session's prompt without completion menus."""

    def read_line(message: str) -> str:
        return prompt_session.prompt(message, completer=None, auto_suggest=None)

    return read_line


def _dispatch_repl_line(documents, line: str, read_line=input) -> bool:
    command = line.strip()
    if not command:
        return False
    if command.casefold() in {"exit", "quit", "q"}:
        return True
    try:
        args = shlex.split(command)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return False
    try:
        dispatch(documents, args, read_line)
    except SystemExit as exc:
        if exc.code in (0, None):
            return True
    return False


def _build_prompt_session(documents=None):
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
        from prompt_toolkit.filters import has_completions
        from prompt_toolkit.history import FileHistory, InMemoryHistory, ThreadedHistory
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.styles import Style
    except ImportError:
        return None

    key_bindings = KeyBindings()

    @key_bindings.add("c-m", filter=has_completions, eager=True)
    def _(event):
        _accept_completion_or_submit(event.current_buffer)

    @key_bindings.add("c-j", filter=has_completions, eager=True)
    def _(event):
        _accept_completion_or_submit(event.current_buffer)

    try:
        # ThreadedHistory loads the file in the background so a large
        # history can never block the input loop.
        history = ThreadedHistory(FileHistory(str(HISTORY_FILE)))
    except OSError:
        history = InMemoryHistory()

    style = Style.from_dict(
        {
            "prompt": "ansicyan bold",
            "bottom-toolbar": "bg:#333333 #cccccc",
        }
    )

    return PromptSession(
        completer=WestminsterCompleter(documents),
        complete_while_typing=True,
        history=history,
        auto_suggest=AutoSuggestFromHistory(),
        bottom_toolbar=_bottom_toolbar(documents),
        style=style,
        key_bindings=key_bindings,
    )


def _bottom_toolbar(documents):
    if not documents:
        return None
    doc_count = len(documents)
    qa_count = sum(
        1 for document in documents for entry in document.entries if entry.kind == "qa"
    )

    def render():
        return (
            "Tab complete · / commands · quiz for flashcards · exit to quit"
            f"  |  Docs {doc_count} · Q/A {qa_count}"
        )

    return render


def _accept_completion_or_submit(buffer) -> None:
    completion = buffer.complete_state.current_completion
    if completion is None:
        buffer.validate_and_handle()
        return
    buffer.apply_completion(completion)
    if completion.text.endswith(" "):
        buffer.start_completion(select_first=False)
    else:
        buffer.validate_and_handle()


def _enable_history() -> None:
    if not sys.stdin.isatty():
        return
    try:
        import atexit
        import readline
    except ImportError:
        return

    try:
        readline.read_history_file(str(READLINE_HISTORY_FILE))
    except (OSError, ValueError):
        pass
    atexit.register(_save_history, readline)


def _save_history(readline) -> None:
    try:
        readline.write_history_file(str(READLINE_HISTORY_FILE))
    except OSError:
        pass


def _has_mesv(entry) -> bool:
    if entry.kind == "qa":
        return bool(entry.question_mesv and entry.answer_mesv)
    return bool(entry.text_mesv)


def _error(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def _clear_screen() -> None:
    print("\033[2J\033[H", end="")


def _color_enabled() -> bool:
    return sys.stdout.isatty()


def _emit(text: str, page: bool = False) -> None:
    """Print text, routing long output through a pager when writing to a TTY."""
    if page and sys.stdout.isatty() and text.count("\n") + 1 > PAGE_THRESHOLD:
        _page(text)
        return
    print(text)


def _page(text: str) -> None:
    less = shutil.which("less")
    if less:
        # -R renders ANSI colors instead of showing raw escape codes;
        # -F quits immediately if it fits one screen; -X keeps the
        # output on screen after quitting.
        try:
            subprocess.run([less, "-RFX"], input=text.encode(), check=False)
            return
        except OSError:
            pass
    # pydoc's fallback pagers don't render ANSI codes, so strip them.
    pydoc.pager(ANSI_ESCAPE_RE.sub("", text))


def _show(documents, argv: list[str]) -> int:
    show_parser = build_show_parser()
    args = show_parser.parse_args(argv)
    document = find_document(documents, args.doc)
    if document is None:
        return _error(f"Unknown document: {args.doc}")
    entry = find_entry(document, args.ref)
    if entry is not None:
        if (args.mesv or args.compare) and not _has_mesv(entry):
            return _error(f"No MESV text available for {document.id} {args.ref}")
        if args.part:
            if entry.kind != "qa":
                return _error("--question and --answer are only valid for catechism entries")
            print(format_entry_part(entry, args.part, mesv=args.mesv))
            if args.proofs:
                proofs = format_proofs(entry, color=_color_enabled())
                if proofs:
                    print()
                    print(proofs)
            return 0
        print(
            format_entry(
                entry,
                color=_color_enabled(),
                proofs=args.proofs,
                mesv=args.mesv,
                compare=args.compare,
            )
        )
        return 0
    if args.part:
        return _error("--question and --answer are only valid for catechism entries")
    # Aggregate by chapter/section prefix: WCF "1", DPW "1" or "1.A".
    if args.ref.isdigit() or document.id == "dpw":
        entries = find_chapter_entries(document, args.ref)
        if entries:
            _emit(
                format_chapter(
                    document,
                    args.ref,
                    entries,
                    color=_color_enabled(),
                    proofs=args.proofs,
                    mesv=args.mesv,
                    compare=args.compare,
                ),
                page=True,
            )
            return 0
    return _error(f"Unknown reference for {document.id}: {args.ref}")


def _dpw_search(documents, argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="ws dpw-search",
        description="Search the Directory for Public Worship of God.",
    )
    parser.add_argument("query", nargs="+", help="Search terms.")
    parser.add_argument(
        "-r",
        "--regex",
        action="store_true",
        help="Treat the query as a case-insensitive regular expression.",
    )
    args = parser.parse_args(argv)
    query = " ".join(args.query)
    dpw = find_document(documents, "dpw")
    if dpw is None:
        return _error("Directory for Public Worship not found in corpus")
    try:
        results = search_entries((dpw,), query, regex=args.regex)
    except ValueError as exc:
        return _error(str(exc))
    _emit(format_search_results(results, color=_color_enabled()), page=True)
    return 0


def _normalize_slash_args(argv: list[str]) -> list[str]:
    if not argv:
        return argv
    first = argv[0]
    if not first.startswith("/"):
        return argv

    command = first[1:].casefold()
    rest = argv[1:]
    if command in {"", "help"}:
        return []
    if command in DOCUMENT_IDS:
        return [command, *rest]
    if command == "q":
        return [*rest, "--question"]
    if command == "a":
        return [*rest, "--answer"]
    if command == "p":
        return [*rest, "--proofs"]
    if command == "m":
        return [*rest, "--mesv"]
    if command in {"list", "search", "dpw-search", "quiz", "stats", "sources", "clear"}:
        return [command, *rest]
    return argv
