---
name: setup
description: Set up the morning paper for a new reader. Check the tools, interview them about their news world, languages, sections, interests and feeds, find and test their outlets, write their files in ~/paper, start the reader server, write the first issue with them, and schedule the morning run. Use when the user says set up, setup, install, get started, asks to schedule the morning run, or asks to change their outlets or sections from scratch.
---

# setup

You are setting up a morning paper for one person. By the end they have their own files in
`~/paper`, a reader on http://localhost:4747, a first issue in front of them, and a run that
writes the next one every morning. Ask with multiple-choice questions (AskUserQuestion), three
or four at a time, your recommendation first; the reader can always type their own answer.
Write their answers into their files in their own words where you can.

Work in this repository. Every command is `uv run paper …` from here.

## 1. Tools

```bash
node --version; uv --version; pdftotext -v
```

Node 22 or later and uv are needed; `pdftotext` (poppler) only for the Hungary outlets. Missing
ones come from Homebrew (`brew install node uv poppler`): ask before installing. Then:

```bash
uv sync && uv run paper init
```

`init` creates `~/paper` from `example/` and the World outlets, and never overwrites a file
that is there.

## 2. The interview

First round:

- **Where they read the news from**: the country they live in, and the countries or regions
  they follow. This decides the outlets.
- **Languages they read** comfortably. Articles in other languages reach them only as digests.
- **The page's language**: English or Hungarian (the only two the page speaks; the articles
  keep their own).
- **When the paper should be ready**: default 05:07, so it is there before they wake.

Second round, what they want beyond the day's news. Offer sections from what they said
(science, ideas, their profession, a sport, culture, a place) and ask which to keep, up to
eight in all. Ask what they are tired of reading, and which writers, journals or newsletters
they already like.

Third round, the topics. Every section that is not the day's news is steered by what they
read: draft three to six topics for each from what they said (plain, a few words each, far
apart: `incentives and markets`, `mind and brain`) and ask for their yes or their changes.
The paper tracks which topics they look at, open and finish, and gives the ones they pass over
fewer chances.

Stop asking when you could state in one sentence what their paper is for and they would agree.

## 3. Outlets: `~/paper/outlets.json`

The engine counts how many independent outlets carry a story, so the list decides what ranks
as news. Start from a preset when it fits (`presets/world.json`: international outlets in
English; `presets/hungary.json`: the Hungarian press across the spectrum and the foreign
papers read from Budapest, the official gazette included), or build one:

- 10 to 25 outlets from the reader's country and the places they follow, across the political
  spectrum and ownership, in languages they read. The more independent newsrooms, the better
  `k` means something; ten copies of one wire service is one source.
- Find each outlet's RSS feed on the web. Prefer a "world" or "top stories" feed over
  "latest".

Each line of the array:

```json
{"id":"guardian","org":"The Guardian","urls":["https://www.theguardian.com/world/rss"],"lang":"en"}
```

- `id`: short, lower case, unique. `org`: the name a reader knows. Two feeds of one newsroom
  (BBC World, BBC UK) get two ids and the same `org`, and count once.
- `urls`: one or more; the first that answers is used. They are RSS or Atom feeds; for an
  outlet with none, its front page and `"kind": "html"`.
- `lang`: the language it publishes in.
- `channel: true` for a wire service (Reuters, AP, AFP, dpa): it relays, so it does not count
  as an independent source unless alone.
- `paywalled: true` for an outlet whose articles are behind a wall: it counts in `k` and is
  never the piece.
- `piece: false` for an outlet the reader wants counted but never handed as the piece.

Then test every outlet and feed, and drop or fix what fails:

```bash
uv run paper check
```

## 4. Their files

Write, in their words where they gave them:

- `~/paper/sections.md`: one line per section, `Name: what belongs in it`, in page order;
  a steered section adds its topics after a `|`:
  `Ideas: essays with an argument | power and institutions, mind and brain, how we know`.
- `~/paper/interests.md`: what they care about and what they are tired of, a short brief.
- `~/paper/feeds.yaml`: the blogs, journals and newsletters they named, with feeds you found
  and `paper check` passed.
- `~/paper/paper.yaml`: `language` (`en` or `hu`) and `morning` (`"HH:MM"`).

The same files can be changed later without you, at http://localhost:4747/settings (the link
at the foot of every issue). Outlets are only removed there; adding one goes through you, so it
is tested first.

## 5. The reader server

```bash
uv run paper install
```

It keeps the page running from login. Tell them in two sentences what this repository lets
Claude do without asking (`.claude/settings.json`): search and fetch the web, run `paper`,
and edit `~/paper`. That is what lets the morning run finish unattended; nothing else is
allowed without a prompt.

## 6. The first issue

Write it now with them watching: follow `.claude/skills/paper/SKILL.md` from step 1. They
approve its tools as they come up. Open http://localhost:4747 when it is published, and tell
them in three sentences how it reads: a piece opens in a clean reader with Next at its end;
selecting text there offers Highlight and Question, and questions are answered in the next
issue; after a finished piece, a card from earlier reading may come due.

## 7. The morning run

The scheduled-tasks tool is in the Claude app's Code tab. Without it (a terminal session),
tell them to open this folder there and say "schedule the morning run", which starts here.

Create a scheduled task in the Claude app (the scheduled-tasks tool), with this repository's
absolute path in place of `<repo>` and their `morning` time as the cron (`7 5 * * *` for
05:07):

- taskId `morning-paper`, title `Morning paper`
- prompt:

  > Write today's issue of the morning paper. This task starts in `<repo>`: run every
  > command there as `uv run paper …`, never with `cd`. Follow `<repo>/.claude/skills/paper/SKILL.md` from step 1 to
  > the end. Nobody is watching: never stop to ask; where the skill leaves a choice, take the
  > one it recommends and list each assumption in the report.

Tell them it runs while the Claude app is open, and on the next launch when it was closed at
that time. End with what their paper is for, in the one sentence from step 2.
