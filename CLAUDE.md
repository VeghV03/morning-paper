# morning-paper

A morning paper Claude writes for one reader. The news engine (`engine/`, Node) reads the
reader's outlets and ranks stories by how many independent outlets carry them; `paper`
(`src/paper/`) wraps it, reads their feeds and saved links, checks the issue Claude writes,
and serves it on http://localhost:4747: the issue, a reader view where the reader highlights
and asks, the cards that come due after a finished piece, and settings. The
repo is also the `paper` plugin and its own marketplace (`.claude-plugin/`): the writing is
`skills/today` (`/paper:today`), a new reader starts with `skills/setup` (`/paper:setup`), and
`scripts/install.sh` puts uv, Node, Python and a copy of this repo in `~/paper/.tools` (macOS,
Ubuntu or Debian, and Windows under Git Bash), run again by the session-start hook in `hooks/`
when the plugin changes. The `paper` tool never calls
a language model.

The reader's files live in `$PAPER_HOME` (default `~/paper`): `outlets.json`, `sections.md`,
`interests.md`, `feeds.yaml`, `inbox.md`, `paper.yaml`, and `taste.md`, `seen.md` and `fields.md` when a section rests on them, are theirs; `issues/`, `digests/`,
`threads.jsonl`, `reads.jsonl`, `marks.jsonl`, `context.json`, `candidates.json`, `.feed.json`, `.tls/`, `.serve.pid`, `.fsrs.json` and `cache/` are written by the run and the
server. `reads.jsonl` and `marks.jsonl` are encrypted line by line (`src/paper/vault.py`), the key's recovery code in the
OS keychain; `context.json` is their plain summary and lives only through the run.

The paper is moving to the cloud (decisions/2026-11-19-always-there.md, D45 on). A scheduled
cloud run (`scripts/cloud-run.sh start`, then `skills/today`, then `finish`) opens the reader's
private data repository into `~/paper`, writes the issue, and seals what changed back with
`paper cloud pack` (`src/paper/cloud.py`): each file whole under the run key in `PAPER_RUN_KEY`,
which `paper cloud key` derives from the recovery code. The reading record never goes there.
The local server below still works until the cloud reader page replaces it.

When the user asks to set this up, follow `skills/setup/SKILL.md`.

## Vendored

- `engine/`: the eight scripts the feed runs and `data/eu-dossiers.json`; comments are in
  Hungarian. `engine/out/` is the engine's own record and grows with each run; it is not
  committed. Its outlets come from `$PAPER_OUTLETS`, which `paper feed` sets.

## Checks

```bash
uv run python -m unittest discover -s tests
```

```bash
uv run paper check
```
