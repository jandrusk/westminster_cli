# Westminster Standards CLI

A small command line tool for reading, searching, and quizzing yourself on the Westminster Standards.

The CLI ships with the Orthodox Presbyterian Church constitutional text for:

- Westminster Confession of Faith (`wcf`)
- Westminster Larger Catechism (`wlc`)
- Westminster Shorter Catechism (`wsc`)
- Directory for the Public Worship of God (`dpw`)

The confession and catechisms are derived from the OPC pages linked from <https://opc.org/confessions.html>. The Directory for Public Worship is the OPC Book of Church Order text at <https://opc.org/BCO/DPW.html>. The constitutional text is the default for the confession and catechisms; the 2025 Modern English Study Version (MESV) is also bundled for those documents and available via `-m`/`--mesv` and `--compare`. Note the OPC preface: the MESV is a study aid and carries no constitutional authority.

The bundled corpus lives in `src/westminster_cli/data/standards.json`. The importer in `scripts/build_opc_corpus.py` can rebuild it from downloaded OPC HTML.

## Installation

You need Python 3.9+ and [uv](https://docs.astral.sh/uv/) installed.

Install `uv` if you do not already have it:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Install the CLI from PyPI:

```sh
uv tool install westminster-standards-cli
```

Then run:

```sh
ws
ws stats
ws wcf 1
ws wsc 1 --question
```

`uv` installs the CLI and its Python dependencies, including `prompt_toolkit`,
from the package metadata.

## Development Install

To try the CLI from a fresh clone without installing it globally:

```sh
git clone https://github.com/normanormata/westminster_cli.git
cd westminster_cli
uv run ws
```

You can also run one-shot commands from the clone:

```sh
uv run ws stats
uv run ws wcf 1
uv run ws wsc 1 --question
```

If you cloned the repo and want your local edits to take effect while you work
on the CLI, install it in editable mode from inside the project folder:

```sh
uv tool install -e .
```

## Run locally

```sh
uv run ws
uv run ws --help
```

Running `ws` with no arguments opens an interactive terminal session. Inside it,
type `/` to see live slash-command suggestions, use arrow keys to select a
command template, run commands without the `ws` prefix, and type `exit` to quit.
Plain commands such as `wcf`, `search`, and `stats` also complete while typing.
Completion is context-aware: after a document id (`wsc `) it suggests references,
and after a reference it suggests `--question`/`--answer`. Command history persists
across sessions, and a bottom toolbar shows quick hints and corpus counts.

Use `quiz` for an interactive flashcard session: it shows a question, waits for
Enter to reveal the answer, records whether you got it, and prints a running score.
Type `s` to skip a card or `q` to stop early. Pass a document id and question
count to shape the session, e.g. `ws quiz wlc 20` (defaults: `wsc`, 10 questions).

`search` matches entries containing all of the given terms; pass `-r`/`--regex`
to treat the query as a single case-insensitive regular expression instead
(`ws search --regex "bapti[sz]ed?"`). Limit the search to one document with
`-d`/`--doc` (for example `ws search --doc dpw baptism` for the Directory for
Public Worship only).

Pass `-p`/`--proofs` to any reading command (`ws wsc 1 -p`, `ws wcf 1.1 -p`,
`ws wcf 1 -p`) to show the OPC scripture proof texts beneath the text,
lettered to match the printed edition. It combines with `-q`/`-a`, and `/p wsc 1`
works as a slash alias.

Pass `-m`/`--mesv` to read the 2025 Modern English Study Version instead
(`ws wsc 1 -m`, `ws wcf 1.1 -m`, `/m wsc 1`), or `--compare` to see the
constitutional and MESV texts together. `-m` combines with `-q`/`-a`
(modern question or answer only) and `-p`.

UV creates and syncs the project environment automatically from `pyproject.toml`
and `uv.lock`.

The repo also includes direct wrappers if you want to run without syncing a UV
environment:

```sh
./ws --help
./westminster --help
./wsc show wsc 1
```

## Commands

```sh
uv run ws list
uv run ws list wsc
uv run ws wsc 1
uv run ws wsc 1 --question
uv run ws wsc 1 --answer
uv run ws wsc 1 --proofs
uv run ws wsc 1 --mesv
uv run ws wsc 1 --compare
uv run ws wcf 1
uv run ws wcf 1.1
uv run ws wcf 1.1 -p
uv run ws wcf 1.1 -m
uv run ws dpw 1.A.1
uv run ws dpw 1
uv run ws search "chief end"
uv run ws search --regex "bapti[sz]ed?"
uv run ws search --doc dpw baptism
uv run ws quiz
uv run ws quiz wlc 20
uv run ws stats
uv run ws sources
uv run ws clear
```

Slash command discovery and aliases:

```sh
uv run ws /
uv run ws /wcf 1
uv run ws /wsc 1 --question
uv run ws /q wsc 1
uv run ws /a wlc 1
uv run ws /p wsc 1
uv run ws /m wsc 1
uv run ws /stats
uv run ws /clear
```

The explicit `show` command still works:

```sh
uv run ws show wcf 1
uv run ws show wsc 1
```

The full command name still works:

```sh
uv run westminster stats
```

After installing the tool, both names are available:

```sh
ws stats
westminster stats
wsc show wsc 1
```

## Test

```sh
uv run python -m unittest discover -s tests
```

## Rebuild the OPC corpus

```sh
curl -L https://opc.org/wcf.html -o /tmp/opc-wcf.html
curl -L https://opc.org/lc.html -o /tmp/opc-lc.html
curl -L https://opc.org/sc.html -o /tmp/opc-sc.html
curl -L https://opc.org/BCO/DPW.html -o /tmp/opc-dpw.html
python3 scripts/build_opc_corpus.py /tmp/opc-wcf.html /tmp/opc-lc.html /tmp/opc-sc.html /tmp/opc-dpw.html
```

The optional fourth argument is the Directory for Public Worship HTML. After a
full rebuild, re-run the scripture proofs and MESV scripts (they apply only to
the confession and catechisms).

## Rebuild the scripture proofs

The proof references come from the OPC "with Scripture proofs" PDFs linked from
<https://opc.org/confessions.html>. After rebuilding the corpus, re-merge them:

```sh
curl -L https://opc.org/documents/CFLayout.pdf -o /tmp/CFLayout.pdf
curl -L https://opc.org/documents/LCLayout.pdf -o /tmp/LCLayout.pdf
curl -L https://opc.org/documents/SCLayout.pdf -o /tmp/SCLayout.pdf
uv run python scripts/add_scripture_proofs.py /tmp/CFLayout.pdf /tmp/LCLayout.pdf /tmp/SCLayout.pdf
```

The script validates that every superscript proof marker in the body text pairs
with a lettered footnote and reports per-document counts before writing.

## Rebuild the MESV text

The 2025 Modern English Study Version comes from the OPC PDFs linked from
<https://opc.org/confessions.html>:

```sh
curl -L https://opc.org/documents/2025_Modern_English_Study_Version_of_The_Confession_of_Faith.pdf -o /tmp/mesv_cf.pdf
curl -L https://opc.org/documents/2025_Modern_English_Study_Version_of_The_Larger_Catechism.pdf -o /tmp/mesv_lc.pdf
curl -L https://opc.org/documents/2025_Modern_English_Study_Version_of_The_Shorter_Catechism.pdf -o /tmp/mesv_sc.pdf
uv run python scripts/add_mesv.py /tmp/mesv_cf.pdf /tmp/mesv_lc.pdf /tmp/mesv_sc.pdf
```

The script validates that the MESV refs exactly match the constitutional
corpus (33 chapters / 171 sections, 196 and 107 questions) before writing.

## Data format

Each document has an id, title, short name, and entries:

```json
{
  "id": "wsc",
  "title": "Westminster Shorter Catechism",
  "short_title": "Shorter Catechism",
  "source": "Orthodox Presbyterian Church constitutional text",
  "source_url": "https://opc.org/sc.html",
  "entries": [
    {
      "ref": "1",
      "kind": "qa",
      "question": "What is the chief end of man?",
      "answer": "Man's chief end is to glorify God, and to enjoy him forever."
    }
  ]
}
```

For confession paragraphs, use `kind: "section"` with `heading` and `text`.

Entries may also carry an optional `proofs` list of scripture proof references,
each with the OPC footnote `letter` and its `references`:

```json
"proofs": [
  { "letter": "a", "references": ["Ps. 86:9", "Rom. 11:36"] }
]
```

Entries may also carry the 2025 MESV text in parallel fields:
`question_mesv`/`answer_mesv` for catechism entries, and
`text_mesv`/`heading_mesv` for confession sections.
