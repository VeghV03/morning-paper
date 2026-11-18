<h1 align="center">Morning paper</h1>

<p align="center">
One issue a day, chosen for you by your own Claude from the outlets you trust,<br>
ranked by how many independent newsrooms carry each story. Read it, close it, done.
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/issue-dark.png">
    <img src="docs/issue-light.png" alt="An issue: the answer to a question the reader marked yesterday, above the day's first section" width="640">
  </picture>
</p>

## Why

A feed never ends, so it never tells you when you are informed. A paper does: it has a last
page. Morning paper gives you one issue every morning, up to three pieces a section, and
nothing goes in to fill a slot. The next morning, a new issue takes the front page.

Three things make it better than a feed:

- **Independent sources decide what is news.** Every morning the news engine reads your
  outlets, groups their headlines into stories and counts the newsrooms behind each one (`k`).
  Two feeds of one newsroom count once, and a wire service counts only when it is alone.
- **One article a story, the best one.** For each story Claude picks the single best account
  you can read whole without paying, usually from the outlet that did the reporting. When a
  story rests on a law, a ruling or a statement, the document itself can be the piece.
- **You keep what you read.** Pieces open one at a time in a clean reader, with the next one
  at the end and a last page after the last. Tap a paragraph to highlight it or ask about it:
  the next issue answers your question, and cards from what you marked and finished come due,
  one after each piece you finish, on a spaced-repetition schedule. A few pieces ask you to
  guess their finding before you read, a running story asks what happened last time, and
  Sunday's issue ends with a crossword of the week you read. Beyond the news, what you look at,
  open and finish steers which topics come back.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/reader-dark.png">
    <img src="docs/reader-light.png" alt="The reader view: a paragraph highlighted and a passage marked as a question, in a Quanta article" width="640">
  </picture>
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/card-dark.png">
    <img src="docs/card-light.png" alt="A card at the end of a finished piece, with the next headline below it" width="640">
  </picture>
</p>

## Set up

You need a Mac and the [Claude app](https://claude.com/download) on a paid plan. In the app's
Code tab, type:

```
/plugin install paper --marketplace VeghV03/morning-paper
```

Then `/paper:setup`. Claude asks three things: where you live, the languages you read, and what
you want beyond the news. It installs the paper's own tools in `~/paper` (nothing system-wide,
no password), starts the reader, writes a quick first issue while you watch, and schedules the
full one for every morning.

Open <http://localhost:4747> with your coffee, or read it on your phone: scan the code in
Settings with the phone's camera, then add the page to your home screen. The first time the
icon opens, type the six digits shown under the code.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/phone-dark.png">
    <img src="docs/phone-light.png" alt="The reader on a phone: a highlighted paragraph, and the next one tapped, with Highlight and Question at the bottom" width="320">
  </picture>
</p>

The morning run needs the Claude app open and the Mac awake, or runs when you next open it.
Each issue uses your Claude plan: Claude searches the web and opens every article it considers.

## How it works

```mermaid
flowchart LR
  A[Claude app, every morning] --> B["/paper:today"]
  B --> C["paper context<br/>what you read"]
  B --> D["paper feed<br/>your outlets → stories by k<br/>your feeds, saved links"]
  C & D --> E[Claude chooses ≤3 a section<br/>answers your questions, writes cards]
  E --> F[paper publish]
  F --> G["localhost:4747<br/>issue · reader · cards · settings"]
  G -->|looked, opened, finished, marked| C
```

Your files and your reading record live in `~/paper` on your Mac. Each morning Claude reads
them to choose the issue, as it reads anything in a conversation. The page answers your Mac and
the phones you paired by scanning that code, and no one else. On your Wi-Fi it travels
unencrypted, so on a shared network someone capturing traffic could read it.

## Make it yours

Everything the paper knows about you is a plain file in `~/paper`. Ask Claude to change it, edit
it yourself, or open Settings at the foot of any issue.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/settings-dark.png">
    <img src="docs/settings-light.png" alt="Settings: each section with what belongs in it and its topics" width="640">
  </picture>
</p>

| File | What it is |
|---|---|
| `outlets.json` | The newsrooms the engine reads and counts. Two presets in `presets/`: World (English) and Hungary. |
| `sections.md` | One line per section, in page order: `Name: what belongs in it`, and topics after a `\|` for a section your reading steers. Eight at most. |
| `interests.md` | What you care about and what you are tired of, in your own words. |
| `feeds.yaml` | Blogs, journals and newsletters you follow; their best new posts go where they fit. |
| `inbox.md` | A link a line; it arrives in the next issue under Saved. |
| `paper.yaml` | The page's language, English or Hungarian. |

## Commands

| | |
|---|---|
| `/paper:setup` | Set up, or set up again. |
| `/paper:today` | Write today's issue now. |
| `~/paper/.tools/bin/paper check` | Which outlets and feeds answer. |

## Where it comes from

Morning paper is the newspaper of [x4r](https://github.com/VeghV03/x4r), a firmware for the
Xteink X4 e-reader, brought to the Mac.

MIT licensed.
