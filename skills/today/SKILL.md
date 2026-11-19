---
name: today
description: Write today's issue of the reader's morning paper. Fetch and rank the news from their outlets, read what they did with past issues, choose up to three original articles for each section in sections.md, write a headline and a lead for each, answer the reader's questions and write cards from what they marked and finished, set the day's games, keep the running stories' threads, and publish the page on localhost. Use when the user says paper, news, today's issue, or when the morning run starts.
---

# paper

Every run you write one issue: for each section, up to three articles worth the reader's
time, chosen by you and written by other people. An issue is finite and it leaves: tomorrow's
replaces it, and what the reader did not read or keep is gone. So nothing goes in to fill a
slot. Everything goes through `~/paper/.tools/bin/paper`; its errors say exactly what to fix.
When it is missing, the paper is not set up: say to run `/paper:setup`, and stop.

Use only the tools the reader allowed at setup, so the morning run never waits at a prompt:
`~/paper/.tools/bin/paper …` in the shell, written exactly so, with no `cd`, pipe or redirect;
Read for files; WebSearch to find articles; `~/paper/.tools/bin/paper read <url>` to open one;
Write and Edit for the issue, digests and threads. Never WebFetch, a subagent, curl, cat, sed
or python.

## 1. Read the state

```bash
~/paper/.tools/bin/paper context
```

It writes what the reader did to `$PAPER_HOME/context.json` and prints a summary; read the
file with Read. The record behind it is encrypted, and this file is its only plain copy:
`paper publish` deletes it, so never copy it anywhere else. When it fails because the record is
locked, stop: line 3 of the report tells the reader to run
`~/paper/.tools/bin/paper restore <recovery code>`. When `recovery_unsaved` is true, line 3 asks
them to open Settings on the computer and save the recovery code. When `published_today` is true, today's issue is out: say so and stop. One
issue a day.

```bash
~/paper/.tools/bin/paper feed
```

It takes a few minutes (the engine downloads every outlet's feed); give it a 10-minute
timeout. It writes the candidates to `$PAPER_HOME/candidates.json` and prints how many of each kind
there are; read the file with Read. The candidates: `news` (stories since the last issue from the reader's
`outlets.json`, ranked by `k`, the number of independent outlets, and for the top stories
`primary` documents: the acts, rulings and statements they rest on), `follow` (new posts from
their `feeds.yaml`), `inbox` (links they saved) and `interests`. It reports the same items
until `paper publish` succeeds, so run it again freely. Its `warnings` are for your report,
not for the reader. A story told in two languages, or split by its angles (a summit, and each leader at it), can arrive as several stories: count it once.

`context` has every piece of the last two weeks (`seen`, `looked`, `opened`, `finished`,
`kept`, `min`, and `topic` and `fit` in steered sections), minutes per section this week, the
threads, the reader's `marks` (highlights and questions, with `answered` and `carded`),
`to_card` (finished pieces with no mark and no card), `cards` (how many, due, reviewed this
week), `games` (what the reader picked in each prediction and link, or that they skipped it,
and the crossword words they did not solve) and `steer`, the morning's topic draw (step 3).

In the cloud run, `context` comes from the brief the reader's phone leaves in the data
repository, and `context.brief` says which day it was made for. It holds decisions, not counts:
pieces carry `opened` but not `finished`, `kept` or `min`; `minutes`, `to_card` and `games` are
empty; `steer` has no `topics` estimates. With no brief yet, `steer` is the flat draw.

The reader's folder is `$PAPER_HOME` (default `~/paper`). `interests.md`, `sections.md`,
`feeds.yaml`, `inbox.md`, `outlets.json`, `paper.yaml`, `taste.md`, `seen.md` and `fields.md` are
theirs: follow them, never edit them (Field's week mark is the one exception, below). Work from these, the
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
  A story the reader already follows or opened a piece on (a thread in `context.threads` with
  `follows`, or an earlier piece in `context.pieces` with `opened`) that has not moved since
  stays out, however high its `k`: the reader already knows it.
- **Every other section**: articles you find on the web that were never in an issue before (any age), that fit its line
  in `sections.md` and `interests.md`, found with WebSearch: essays, research written for
  readers, reporting with a finding. Prefer the piece with an argument or a finding over the piece with an opinion. No
  paywalled pages, never the same site twice in an issue. The best new posts from
  `feed.follow` go where they belong; a post that fits no section, or is not an article, is
  left out.
- **Sections that rest on the reader's own files**, when `sections.md` has them:
  - **Film**: arrivals in cinemas and on the services its line names, chosen by `taste.md`
    and never a title in `seen.md`. Up to three a week: count the Film pieces in this week's
    earlier issues first. The piece is the best free review or the fullest notice of the
    title; its lead says which line of `taste.md` it answers.
  - **Field**: this week's field is the first line of `fields.md` without a week mark. On the
    week's first issue, two pieces: the best free introduction to the field on the web, and
    its primary text (a classic work of the field that can be read free and whole). Then add
    the week to that line, `(2026-w48)`: the one edit you make to a reader's file. On other
    days the section is empty.
  - **Football** (or any sport): analyses of how a team plays, how a club is run, the numbers
    behind a match, the clubs its line names first. On the week's first issue, the best piece
    on each named club's week, if there is one.

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

Before choosing, open each candidate with `~/paper/.tools/bin/paper read <url>`. It prints the article as
the reader will see it, or says there is none: then it is not a piece, however good the page
looks in a browser.

## 3. Learn from the reader

A section is **steered** when its line in `sections.md` lists topics after a `|`. Every piece
in it carries `topic`, the one topic on that list it is mostly about, and `fit`: `tries` for the
piece that explores (below), `fits` for the rest. The page writes each steered piece's why line
from these two and the reader's record; you write nothing for it.

`context.steer` gives, per steered section, the morning's draw from the paper's topic model:
`order`, the section's topics in the order to prefer; `try`, the topic with the least `evidence`;
`tries`, all of them from the least evidence up; and
for each topic its `estimate` (the share of its pieces expected to turn out well) and
`evidence` (how many recent showings that rests on). The model learns from what the reader
finished, kept, marked, opened, passed over, remembered as a card, or asked for less of. The
draw is the same however often you run `paper context` in a day. Apply these rules, in order:

1. **Worth first.** The rules choose only between pieces of similar worth. They never let a
   weak piece in, and never keep a strong one out.
2. **Follow the order.** Between pieces of similar worth, the one whose topic comes earlier in
   `order` takes the slot.
3. **One try.** Each steered section gives one slot to a piece on its `try` topic, with `fit`
   `tries`. When no strong piece on it exists, take the next topic in `tries`; when none is
   strong either, the section has no try that day.
4. A `silent` section (shown for 28 days, nothing opened in them) gets one piece. An open
   restores three.

News sections are not steered: they stay ranked by `k`. Name in your report each rule that
changed a choice, and each section that had no try.

## Answers and cards

What the reader marks in the reader comes back to them.

- **Answers.** For each mark with `kind` `question` and not `answered`, open its piece with
  `~/paper/.tools/bin/paper read` and answer it: `{"id":"a-<today>-<n>","answer":"<mark id>","text":"…"}`,
  in the page's language, 120 words at most, plain sentences that start from the passage. A
  mark is the whole paragraph the reader tapped, so a question is the wish to have it
  explained: say what the passage means and what the reader needed to know; never pad.
Answers and cards are lines of the issue file, after its pieces.

- **Cards.** For each mark not `carded`, one or two cards on what it says. For each piece in
  `to_card`, one card on its main finding. For each game in `context.games` with `right` false
  and not `carded`, one card on the right answer, `from` the game's id; its piece then gets no
  `to_card` card, which would ask the same thing. At most 12 an issue;
  marks first, then missed games, newest first.

```json
{"id":"c-2026-11-18-1","card":"flip","front":"What did the 1998 supernova surveys show?","back":"The expansion of the universe is speeding up: the first evidence for dark energy.","from":"h-…"}
{"id":"c-2026-11-18-2","card":"choice","prompt":"About how much of the universe's energy is dark energy?","options":["5%","25%","70%"],"answer":2,"from":"r-2026-11-17-4"}
```

One fact a card, in the page's language, answerable without the article open. A `flip` front
is a question of 25 words at most, its back the answer in one or two sentences. A `choice` has
three options of the same kind and length, the wrong two ones a reader could believe; `answer`
is the right one's index. `from` is the mark or piece it comes from. A card on a passing
detail, or one that only tests the wording, is worse than none. Cards come due in the reader,
one after each finished piece, on a schedule the reader's answers set.

## Games

Three games, each a line of the issue file. They ask the reader to recall or guess before
reading, which is what makes the reading stick; a game on a detail is worse than none.

- **Predictions.** On up to three pieces with one clear finding (a study's result, a vote's
  outcome, a number), ask what it is before the piece opens. The reader picks, reads, and sees
  the answer at the end. Until then the reader sees your headline, not the article's own
  title, so on a predicted piece neither `head` nor `lead` may give the finding away.
- **Links.** When a piece carries a thread and `context.pieces` has an earlier piece of that
  story the reader `opened`, ask what happened in it. The story's updates follow the answer.
  One game a piece: never a link and a prediction on the same one.

```json
{"id":"p-2026-11-18-1","predict":"r-2026-11-18-4","prompt":"How much faster is the universe expanding than the standard model says?","options":["About 1%","About 8%","About 30%"],"answer":1}
{"id":"l-2026-11-18-1","link":"r-2026-11-18-2","from":"r-2026-11-15-1","prompt":"What did parliament do with the budget last week?","options":["Passed it","Sent it back","Delayed the vote"],"answer":2}
```

Three options of the same kind and length, as on a choice card, in the page's language.

- **The crossword, Sundays only.** Six to twelve names and terms from pieces of the past
  week the reader `opened`, each one word of 3 to 9 letters, no spaces or digits; the clue
  (90 characters at most) is answerable from the piece, which `piece` names. Prefer short
  words that share letters: `paper publish` lays them on a 9 by 9 grid and refuses the
  crossword when fewer than six cross.

```json
{"id":"x-2026-11-22","crossword":[{"answer":"Danube","clue":"The river the new bridge crosses","piece":"r-2026-11-19-3"}]}
```

## 4. Threads: `$PAPER_HOME/threads.jsonl`

A running story is the paper's promise: each morning the reader picks up every story they
follow from where they left it, sees what changed since, and nothing they already know. The
page puts these stories first, under Since you left, from the threads you keep here.

A thread is `{"id":"t-<slug>","title","since","entries"}`, one a line. `since` is the day the
story was first in an issue. `entries` are the story's developments, oldest first, one for
each day it moved:

```json
{"id":"t-hu-budget","title":"Hungary's 2027 budget","since":"2026-11-15","entries":[{"day":"2026-11-15","text":"The government tabled a budget with a 4.1% deficit.","piece":"r-2026-11-15-2"},{"day":"2026-11-17","text":"The Fiscal Council called the deficit target unreachable."}]}
```

- `text`: what happened that day, in the page's language (`paper.yaml`), 280 characters at
  most: one or two plain sentences a reader can follow without the article. Never what an
  earlier entry already said.
- `piece`: the piece of an issue that carried that day's news, when one did. Leave it out for a
  development you found but put no piece on. It is how the page knows the reader opened the
  story.

A story becomes a thread the second time it is among an issue's pieces (compare with
`context.pieces` and the threads already in the file), not on its first day: write an entry for
the first day too, naming its piece. Then the piece carries `"thread":"t-<slug>"`.

A story the reader named at setup is a thread from that day and theirs (`follows`, no
`left_off` until they read it); keep it like any other.

Every morning, for each thread whose story moved, add today's entry, with `piece` when today's
issue carries it.

**Missed days.** When `context.last_issue` is more than a day before `context.today`, the run
did not happen on the days between (the computer was asleep or the app closed), and the reader was
promised those days too. Before anything else in this section, for each thread fill in what
happened on each missed day, up to 14 days back: one entry a day the story moved, dated the day
it happened, without `piece`. Start from `feed.news`, which covers the days since the last
issue as far as the outlets' feeds still hold them, and search the web for the rest. A day the
story did not move gets no entry. Only then apply the two-week drop, so a story is not dropped
for news you have not looked for yet. A story the reader follows (`follows` in `context.threads`) can move without
a piece worth reading: the entry alone reaches them under Since you left. `new` says how many
entries they have not seen yet. Write no entry for a story that did not move.

The entries together stay under 4000 bytes: past that, shorten the oldest. Drop a thread whose
newest entry is more than two weeks old, after filling in missed days; 32 at most. A thread from before entries, with one `body` paragraph,
reads as one entry; rewrite it as entries when its story next moves.

## 5. Publish

```bash
~/paper/.tools/bin/paper publish
```

It checks the issue and the threads, moves the feed cursor, takes the saved links out of
`inbox.md`, and prints the page's address. When it refuses, fix what it names and run it
again. Once it succeeds the issue is out: never change it. When it says the server is not running, line 3 of the report tells the reader to run
`~/paper/.tools/bin/paper install` once.

## 6. Report

Your last message is the report: three lines, nothing before or after them.

1. The pieces by section, then answers, cards and games: `World 3 · Science 1 · Saved 2 · 1 answer · 4 cards · 2 games`.
2. Each steering rule that changed a choice and each steered section with no try, or `no change`.
3. What the reader has to do, such as starting the server, in one sentence; else `nothing to do`.

Each line is one sentence of 30 words at most. Feed warnings, stories left out and the choices
you made stay out of the report: the issue shows them. When nobody is watching (the morning
run), never stop to ask: take the choice this skill recommends.
