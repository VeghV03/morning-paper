---
name: paper
description: Write today's issue of the reader's morning paper. Fetch and rank the news from their outlets, read what they did with past issues, choose up to three original articles for each section in sections.md, write a headline and a lead for each, keep the running stories' threads, and publish the page on localhost. Use when the user says paper, news, today's issue, or when the morning run starts.
---

# paper

Every run you write one issue: for each section, up to three articles worth the reader's
time, chosen by you and written by other people. An issue is finite and it leaves: tomorrow's
replaces it, and what the reader did not read or keep is gone. So nothing goes in to fill a
slot. Everything goes through `uv run paper` in this repository; its errors say exactly what
to fix.

Use only the tools this repository allows without asking, so the morning run never waits at a
prompt: `uv run paper …` in the shell, from the folder you start in, with no `cd`, pipe or
redirect; Read for files; WebSearch to find articles; `uv run paper read <url>` to open one;
Write and Edit for the issue, digests and threads. Never WebFetch, a subagent, curl, cat, sed
or python.

## 1. Read the state

```bash
uv run paper context
```

When `published_today` is true, today's issue is out: say so and stop. One issue a day.

```bash
uv run paper feed
```

It takes a few minutes (the engine downloads every outlet's feed); give it a 10-minute
timeout. It writes the candidates to `$PAPER_HOME/candidates.json` and prints how many of each kind
there are; read the file with Read. The candidates: `news` (stories since the last issue from the reader's
`outlets.json`, ranked by `k`, the number of independent outlets, and for the top stories
`primary` documents: the acts, rulings and statements they rest on), `follow` (new posts from
their `feeds.yaml`), `inbox` (links they saved) and `interests`. It reports the same items
until `paper publish` succeeds, so run it again freely. Its `warnings` are for your report,
not for the reader. A story told in two languages arrives as two stories: count it once.

`context` has every piece of the last two weeks (`seen`, `opened`, `finished`, `kept`, `min`),
minutes per section this week, and the threads.

The reader's folder is `$PAPER_HOME` (default `~/paper`). `interests.md`, `sections.md`,
`feeds.yaml`, `inbox.md`, `outlets.json` and `paper.yaml` are theirs: follow them, never edit
them. Work from these, the
feed and web search.

## 2. The issue: `$PAPER_HOME/issues/<today>.jsonl`

`sections.md` has one line per section, in the page's order: its name and what belongs in
it. For each section write up to three pieces, the best first. Three when three are worth
reading, fewer when they are not, none when nothing is. A thin section is right; a filled one
is wrong.

A piece is an original article, whole, in its own language, linked by `url`, one JSON object
a line:

```json
{"id":"r-2026-11-18-1","section":"world","url":"https://…","head":"Five EU states plan return hubs in Rwanda","lead":"Denmark, the Netherlands, Austria, Sweden and Greece would send rejected asylum seekers there."}
```

- `id`: `r-<today>-<n>`, counting from 1.
- `section`: the section's name in lower case, accents dropped, spaces as `-`
  (`Long reads` is `long-reads`). `paper publish` names the valid ones when you get it wrong.
- `head`: the headline, 60 characters at most, in the piece's language. It says what happened
  or what the piece shows, in the plainest words. Never a teaser, a question or a pun.
- `lead`: what the piece says, 140 characters at most, in the piece's language: the one
  sentence you would tell someone deciding whether to read it. It adds to the headline, never
  repeats it.

What each kind of section takes:

- **News sections** (World, a country, any section about the day's events): the day's biggest
  stories from `feed.news`, by `k`. For each, the single best article on it that can be read
  whole without paying: the fullest account from the outlet that did the reporting, before a
  wire rewrite. When the story rests on a document (a law, a ruling, a statement) and the
  document is short and readable, the document itself may be the piece. Never two pieces on
  one story; never the same outlet three times in a section. A source with `"piece": false`
  (a paywalled outlet, or one the reader marked as never the piece) counts in `k` and is never
  the piece;
  when a story has no other source, find the piece on the web or leave the story out.
- **Every other section**: articles you find on the web, fresh each issue, that fit its line
  in `sections.md` and `interests.md`, found with WebSearch: essays, research written for
  readers, reporting with a finding. Prefer the piece with an argument or a finding over the piece with an opinion. No
  paywalled pages, never the same site twice in an issue. The best new posts from
  `feed.follow` go where they belong.

A **digest** is the one piece you write: for an article worth reading in a language the reader
does not read (`paper.yaml` and `interests.md` say which they do). In the reader's language,
at most 450 words, in `$PAPER_HOME/digests/<id>.md`: what it reports and argues, its facts and
figures, a few short key lines translated and quoted. Never a full translation: that
republishes someone else's article. The piece adds `"digest": true` and keeps the original as
`url`. At most two an issue.

A link the reader saved (`feed.inbox`) is no section's piece. It arrives already kept, with a
headline you write from its page, at most eight an issue (the rest wait for the next):

```json
{"id":"r-2026-11-18-12","saved":true,"url":"https://…","head":"…"}
```

Before choosing, open each candidate with `uv run paper read <url>`. It prints the article as
the reader will see it, or says there is none: then it is not a piece, however good the page
looks in a browser.

## 3. Learn from the reader

From `context.pieces` and `context.minutes`: sections, topics and outlets the reader passes
over or leaves unfinished get fewer pieces; finished and kept ones the better slots. A piece
not `seen` was never in front of them; it says nothing about the piece. An `opened` piece that
is not `finished` was started and left. Say in your report what you changed because of it.

## 4. Threads: `$PAPER_HOME/threads.jsonl`

A story that runs for days gets a thread: `{"id":"t-<slug>","title","body","since","updated"}`.
`body` is the story so far up to but not including today's news: who, what is at stake, what
happened in order, in plain words in the page's language (`paper.yaml`), one paragraph, 600 bytes at most.
The reader sees it above the piece, open when its text is new to them, so change the text
only when the story moved.

A story becomes a thread the second time it is among an issue's pieces (compare with
`context.pieces` and the threads already in the file), not on its first day. Then the piece
carries `"thread":"t-<slug>"`. Drop a thread that had no news for two weeks; 32 at most.

## 5. Publish

```bash
uv run paper publish
```

It checks the issue and the threads, moves the feed cursor, takes the saved links out of
`inbox.md`, and prints the page's address. When it refuses, fix what it names and run it
again. Once it succeeds the issue is out: never change it. When it says the server is not running, tell the reader to run `uv run paper install`
once.

## 6. Report

Your last message is the report: three lines, nothing before or after them.

1. The pieces by section: `World 3 · Science 1 · Saved 2`.
2. What you changed because of the reading record, or `no change`.
3. Every warning from `feed` and `publish`, and each choice you made where this skill left one,
   a few words each; `none` when there are none.

When nobody is watching (the morning run), never stop to ask: take the choice this skill
recommends and name it in line 3.
