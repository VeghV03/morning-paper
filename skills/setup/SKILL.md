---
name: setup
description: Set up the morning paper for a new reader in a few minutes. Install the paper's own tools in ~/paper, ask three questions (where they live, the languages they read, what they want beyond the news), write their files, ask which running stories they follow, start the reader, write a quick first issue while they watch, pair their phone and schedule the morning run. Use when the user says set up, setup, install, get started, or asks to schedule the morning run.
---

# setup

You are setting up a morning paper for one person, and it should take minutes. By the end they
have their files in `~/paper`, a reader on http://localhost:4747, a first issue in front of
them, and a run that writes the next one every morning. Ask with multiple-choice questions
(AskUserQuestion), your recommendation first; the reader can always type their own answer.
Never ask what a default answers: they change everything later in Settings.

Every command is `~/paper/.tools/bin/paper …`, written exactly like that, so the permission
rules in step 4 match it.

It runs on macOS, Windows and Ubuntu or Debian. On Windows the paper needs Git for Windows, whose
Git Bash runs these commands: if your shell tool is PowerShell, not Bash, stop before anything
else and tell them to install it from https://git-scm.com/downloads/win, then reopen the Claude
app and run setup again. On another Linux, say the morning run needs the Claude app, which is
for Ubuntu and Debian, before going on.

## 1. The tools

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/install.sh" && ~/paper/.tools/bin/paper init
```

It puts uv, Node, Python and the paper in `~/paper/.tools` (about 240 MB, pinned builds checked
against their checksums; nothing system-wide, no password), then creates the reader's files from
the defaults, never overwriting one that is there. Tell them that in one sentence before it runs.
It also reinstalls itself, quietly, when the plugin updates.

## 2. Three questions

One round, three questions:

1. **Where they live**, which picks the outlets: the World preset (international outlets in
   English) or the Hungary preset (the Hungarian press across the spectrum, and the foreign
   papers read from Budapest). Anywhere else, World; say their own country's outlets can be
   added later, which you test first.
2. **The languages they read**, and with it the page's own language, English or Hungarian, the
   two the page speaks. Articles keep their own language; one they cannot read reaches them as
   a digest.
3. **What they want beyond the news**, several at once: science, ideas, culture, their
   profession, a sport, a place. Up to five; the news sections come from the preset.

## 3. Their files

Write them without asking more; one line each tells them what you wrote.

- `~/paper/outlets.json`: the chosen preset, `cp "${CLAUDE_PLUGIN_ROOT}/presets/<world|hungary>.json" ~/paper/outlets.json`.
- `~/paper/sections.md`: one line per section, in page order, `Name: what belongs in it`. The
  news first: `World`, and with the Hungary preset `Hungary` before it, named in the page's
  language; then what they chose. Each section beyond the news is steered
  by what they read: give it three to five topics after a `|`, plain, a few words each, far
  apart: `Science: research written for readers | physics and cosmology, life and medicine, mind and brain`.
- `~/paper/interests.md`: two or three sentences from their answers.
- `~/paper/paper.yaml`: `language` (`en` or `hu`) and `morning: "05:07"`.

Feeds, writers and journals they like can come later, in Settings or by asking you.

## 4. The reader, and what runs unattended

```bash
~/paper/.tools/bin/paper install
```

It keeps the page running from login and reaches the phone on the home Wi-Fi. When the computer
asks whether Python may accept incoming connections (macOS), or shows a Windows Security alert
for Python, Allow lets the phone in; on Windows, allow private networks only.

What they open, finish, mark and ask is kept encrypted, with the key in the computer's keychain
(Credential Manager on Windows, GNOME Keyring or KWallet on Linux). If a command says there is no
keyring, stop and tell them what it says: the paper will not keep the key anywhere weaker.
Open <http://localhost:4747/settings> for them: the recovery code is at the top. Ask them to save
it in their password manager and press the button under it. Say once, plainly: without the code,
a new computer or a lost keychain means the record starts again from nothing.

The morning run must finish with nobody there to approve its steps. Ask once whether to add
these rules to `~/.claude/settings.json` (`permissions.allow`, keeping what is there):
`Bash(~/paper/.tools/bin/paper:*)`, `WebSearch`, `Read(~/paper/**)`, `Edit(~/paper/**)`,
`Write(~/paper/**)`. Say what they allow: the paper's own command, web search, and its own
folder; nothing else runs without a prompt. Without them, the run waits for approvals.

## 5. A quick first issue

Write it now, with them watching, by `${CLAUDE_PLUGIN_ROOT}/skills/today/SKILL.md`, quick. Its
first section, Since you left, lists only the stories the reader follows, so first ask for them.

1. Skip `paper context`: there is no reading yet. Run `~/paper/.tools/bin/paper feed`, and read
   `news` and `follow`.
2. Ask one question, several answers allowed: which running stories they follow now. Offer the
   four biggest stories in `news` that have run for days, each named plainly in a few words;
   they type their own as the answer they add. None is an answer too.
3. For each story they chose, find what happened in it over the last seven days: `news` first,
   then web search. Write its thread by section 4 of the run, one entry for each day it moved,
   oldest first. A story with no news in seven days gets one entry, its latest development.
   Then `~/paper/.tools/bin/paper follow t-<slug> …` with their ids.
4. One piece a section, two at most: the news from the top stories by `k`, the sections beyond
   it from `follow` or a top story that fits. A piece on a story they chose carries its
   `thread`, and that day's entry names the piece. Open only the articles you choose; no other
   web search. Every piece in a steered section has `fit` `tries`: nothing has been read yet,
   so its why line says it is something new.
5. No answers, cards or games: there is nothing to build them on yet.
6. Publish, and open http://localhost:4747. No report: they are watching.

Then tell them in three sentences how it reads: a piece opens in a clean reader with Next at
its end; tapping a paragraph offers Highlight and Question, and questions are answered in the
next issue; each issue opens with what changed in the stories they follow since they last read
them, and opening a piece of any running story follows it too.

## 6. The phone

Ask whether they want it on their phone too. If so: Settings on the computer shows a code; they scan
it with the phone's camera. The page that opens takes them through it once: install the paper's
certificate, trust it (on an iPhone that is two places in Settings, both named on the page), then
Open the paper, which pairs the phone over HTTPS. Then Share, Add to Home Screen. The first time
the home-screen icon opens, it asks for the six digits shown under the code. A phone that cannot
open the page from the code (older Android phones, some Windows networks) types the numeric
address shown under it instead. If they ask what
the certificate lets the computer do: it can vouch only for this computer's `.local` name and
home-network addresses, never for another site.

## 7. The morning run

Create a scheduled task with the scheduled-tasks tool (in the Claude app's Code tab; in a
terminal, tell them to say "schedule the morning run" in the app, which starts here):

- taskId `morning-paper`, title `Morning paper`, working folder `~/paper`, cron `7 5 * * *`.
- prompt:

  > /paper:today
  >
  > Nobody is watching: never stop to ask; where the skill leaves a choice, take the one it
  > recommends and list each assumption in the report.

Tell them it runs while the Claude app is open and the computer awake, and on the next launch when
it was not. End with what their paper is for, in one sentence.
