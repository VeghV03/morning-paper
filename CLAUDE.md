# morning-paper

A morning paper Claude writes for one reader. The news engine (`engine/`, Node) reads the
reader's outlets and ranks stories by how many independent outlets carry them; `paper`
(`src/paper/`) wraps it, reads their feeds and saved links, checks the issue Claude writes,
and serves it on http://localhost:4747 with a reader view that records what was read. The
writing is the `/paper` skill; a new reader starts with `/setup`. The `paper` tool never calls
a language model.

The reader's files live in `$PAPER_HOME` (default `~/paper`): `outlets.json`, `sections.md`,
`interests.md`, `feeds.yaml`, `inbox.md` and `paper.yaml` are theirs; `issues/`, `digests/`,
`threads.jsonl`, `reads.jsonl`, `candidates.json`, `.feed.json` and `cache/` are written by the run and the
server.

When the user asks to set this up, follow `.claude/skills/setup/SKILL.md`.

## Vendored

- `engine/`: the eight scripts the feed runs and `data/eu-dossiers.json`; comments are in
  Hungarian. `engine/out/` is the engine's own record and grows with each run; it is not
  committed. Its outlets come from `$PAPER_OUTLETS`, which `paper feed` sets.
- `dashboard/` is x4r's interests dashboard, copied unmodified.

## Checks

```bash
uv run python -m unittest discover -s tests
```

```bash
uv run paper check
```
