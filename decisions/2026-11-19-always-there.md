# 2026-11-19 · Always there

What comes after the redesign (D1 to D32), aimed at making the paper the one the reader reaches
for every morning.

Premise: no real morning has run yet (no `~/paper` on the development Mac); steps 1 to 4 were
checked on a demo. The structural gap: the paper lives on a computer that sleeps, and the phone
reads from that computer, so a closed laptop or a reader away from home means no paper.

## D33 · Who it is for
**Chosen:** one reader first, until it holds up daily.
**Not chosen:** Claude users like the reader (more presets and setup polish now); anyone (a
hosted version, the record off the computer).
**Accepted cost:** presets stay World and Hungary; other readers wait.

## D34 · What to build first
**Chosen:** always there. The phone keeps the latest issue to read anywhere and syncs reading
back at home.
**Not chosen:** two weeks of use before building anything; more countries; issue quality checks.
**Accepted cost:** a second copy of the reader's reading on the phone, for a while.

## D35 · When the issue is written
**Chosen:** as now, at 5:07 or when the computer next wakes; the phone shows the issue it has
until the new one arrives.
**Not chosen:** an evening edition (no overnight news); waking the computer on a schedule (admin
password, per system, the app must still be open); a cloud run (the record leaves the computer).
**Accepted cost:** some mornings the new issue arrives late.
**Superseded by D45:** the issue is written in the cloud.
**Revised by D41:** the phone saves the new issue only when the paper is opened at home while
the computer is awake.

## D36 · Away from home
**Chosen:** a saved copy on the phone; highlights, questions and reads wait there and sync at
home.
**Not chosen:** home only, as now; reaching the computer from outside (a tunnel puts the server
on the internet).
**Accepted cost:** a question asked on the bus is answered a day later.
**Superseded by D45 and D46:** the phone syncs with storage, not the computer.

## D37 · What the phone keeps
**Chosen:** the latest issue, with every piece's full text and the reader's story pages.
**Not chosen:** the last seven days; everything unread.
**Accepted cost:** yesterday's unread pieces are gone offline once today's issue arrives.

## D38 · Cards offline
**Chosen:** the phone takes the cards due by the end of the day it syncs; they come after
finished pieces offline as at home, and are rescheduled when the reviews reach the computer.
**Not chosen:** no cards away from home.
**Accepted cost:** a card that falls due later in the day waits for the next sync.

## D39 · The phone's copy
**Chosen:** kept in the paper's own storage on the phone, protected by the phone's passcode
encryption; what the reader did offline is cleared once it reaches the computer.
**Not chosen:** the paper's own encryption on the phone (its key would sit beside the data);
recording nothing offline (the learner and Since you left would never hear of it).
**Accepted cost:** while it waits, the offline record is not encrypted by the paper itself.

## D40 · Showing the saved copy
**Chosen:** nothing; the issue's date says which issue it is.
**Not chosen:** a quiet "Saved copy" line.
**Accepted cost:** the reader may not notice something is waiting to sync.

## Unverified, to test on a real phone
- An iPhone registers the offline worker on a page served under the paper's own certificate
  once it is trusted (I think so; no source confirms it).
- iOS keeps a home-screen app's storage past seven days without use (reported both ways; a
  daily reader never reaches it).
- Android: the same worker and certificate trust are reasoned about, not tried.

## D41 · When the phone gets the new issue
**Chosen:** accepted as it is: the phone saves the new issue when the paper is opened at home
while the computer is awake. iOS lets a web app fetch nothing in the background.
**Not chosen:** a scheduled wake at 5:00 on top; an evening edition.
**Accepted cost:** a laptop asleep at 5:07, or a morning the reader leaves without opening the
paper, means yesterday's issue on the way.

## D42 · Games away from home
**Chosen:** the saved copy carries the answers, so predictions and the crossword work anywhere.
**Not chosen:** games only at home.
**Accepted cost:** the answers sit in the phone's copy; only the reader could peek.

## D43 · The time of what was done offline (retired by D78)
**Chosen:** the phone's clock, when it happened, kept no earlier than the phone's last sync and
no later than the moment it reaches the computer.
**Not chosen:** the time it reaches the computer.
**Accepted cost:** within those bounds, the phone's clock is trusted.

## D44 · Test on a real iPhone first
**Chosen:** the smallest offline copy (the pages already opened, saved as they are opened) on
the demo server, opened from the home-screen icon in airplane mode, before the full build.
**Not chosen:** build it all, then test.
**Accepted cost:** about ten minutes with the phone before the build goes on.
**Outcome:** the certificate could not be added on the iPhone, and the reader judged the
own-certificate path overkill. It is dropped (D45).

## Follows from earlier decisions, not asked
- Saving the issue for the phone never counts as opening it: only a piece the reader opens is
  an open (D25). Pieces are saved through a route that logs nothing.
- A piece the paper could not save opens at its outlet, as now; away from home the phone still
  has mobile data, only not the computer.
- The phone waits a few seconds for the computer before falling back to its copy, so a tap
  away from home does not hang.
- The offline copy runs only over HTTPS on the phone; the computer's own localhost page always
  shows the live server.

## The cloud turn

The reader could not add the certificate on the iPhone and wants Claude to work in the cloud,
with as much privacy and security as that allows, using algorithms, data science and local
models (not only language models). What follows replaces the computer as the paper's home.
D37 to D43 carry over, with "the computer" read as "the morning run and storage".

Verified (code.claude.com, routines and cloud-environments pages, 2026-11-19): cloud scheduled
tasks run on Anthropic's machines with the laptop closed (Pro and up, research preview); each
run clones a GitHub repository and can push to it as the reader; network access is an
allowlist or full; a network secret is a key the run uses for named hosts without seeing it.

## D45 · The computer leaves the loop
**Chosen:** a cloud run writes the issue; phone and computer only open the paper in a browser.
Setup starts from the Claude app; three steps are the reader's own, since they hold credentials
or settings Claude does not touch: creating the GitHub token, setting the cloud environment's
network and key, and opening the setup link on the phone.
**Not chosen:** the computer as the home of the record, making the brief whenever awake.
**Accepted cost:** the local server, the paper's own certificate and pairing, the keychain
vault, the login services and most of the installer (steps 2 and 3, D1, D21 to D24) retire.
**Supersedes:** D1's link encryption and keychain; D35; D36's sync with the computer.

## D46 · Where the record is decrypted
**Chosen:** only on the reader's devices. The learner runs in the browser; storage holds
ciphertext; the run gets a brief.
**Not chosen:** inside the morning run, with the key in its environment.
**Accepted cost:** the topic model and FSRS move from Python to JavaScript; the records of
phone and computer merge through storage.
**Why:** the run reads untrusted articles with a shell and network access; an injected
instruction could send out a key it holds. Without the record's key, the most it can leak is
the brief.

## D47 · The brief
**Chosen:** decisions only: per steered section the topic order and try; followed stories with
the date last read; the reader's highlights and questions; pieces to make cards from; silent
sections. No counts, no reading times.
**Not chosen:** everything `paper context` gives today, counts included.
**Accepted cost:** anything new Claude should weigh needs a change on the device first. Pieces
to make cards from tell Claude which pieces were finished. The brief is refreshed only when the
paper is opened, so after days away the run works from the last one.

## D48 · Algorithms first
**Chosen:** the public side, in the cloud on public news: embeddings to group stories and drop
duplicates, and novelty scoring so Since you left shows only what is new.
**Not chosen:** a personal interest model on the device first (nothing real to learn from yet,
untested on iPhone); porting only, algorithms later.
**Accepted cost:** a model download in the cloud setup.
**Open until step 4:** whether embeddings replace the engine's grouping of headlines or sit on
top of it.

## D49 · Storage
**Chosen:** GitHub. A private repository holds only ciphertext; the reader page is served by
GitHub Pages; the phone writes back through GitHub's API (which answers browser pages, checked
2026-11-19) with a token limited to that one repository.
**Not chosen:** looking further first (Cloudflare needs another account and a small server; no
source confirms a run can write to a claude.ai page).
**Accepted cost:** GitHub sees when the reader syncs and how much; a stolen phone token could
read ciphertext and write junk until it is revoked.

## D50 · The run's network
**Chosen:** full access, so Claude can open any outlet, document or source.
**Not chosen:** an allowlist of the reader's outlets and named sources.
**Accepted cost:** an article with injected instructions could send out what the run holds,
which by D46 and D47 is the brief, never the record, and the key the run holds for it. Past
briefs stay in a private repository that key alone does not reach.

## D51 · The local version
**Chosen:** retired; the paper runs one way.
**Not chosen:** local or cloud, chosen at setup.
**Accepted cost:** no paper without GitHub and a Claude plan with cloud tasks; the code of steps 2
and 3 goes. Cloud tasks are a research preview: if they change, the paper has no other way to
run.

## D52 · Build order
**Chosen:** the paper first: 1 the cloud run writes an encrypted issue; 2 the reader page opens
it; 3 the record and the learner on the device; 4 the public-side algorithms.
**Not chosen:** the record first.
**Accepted cost:** the first issues are steered only by the reader's own files.

## D53 · The reader page's code
**Chosen:** pinned. The page loads only a version the reader approved; an update asks once
before it runs.
**Not chosen:** always the latest from the plugin's GitHub Pages.
**Accepted cost:** one tap per update, and the machinery to check the version.
**Why:** the page holds the key on the device; whoever can change its code could take the record.

## D54 · Keys
**Chosen:** one recovery code (step 2's, 24 characters) gives two keys. The run key opens
everything the run reads or writes: the reader's files, the brief, issues, the engine's own
record. It sits in the cloud environment's variables. The record key opens the reading record
and never leaves the reader's devices. Each file in the data repository is sealed whole, with
its path bound in, so files cannot be swapped.
**Not chosen:** issues sealed for the devices alone (the run could not reread its own past issues).
**Accepted cost:** with the run key and a way into the private repository, someone could read
past issues and briefs, never the record.

## D55 · The data repository
**Chosen:** a private repository of the reader's, holding sealed files only.
**Not chosen:** building everything locally before creating it.
**Accepted cost:** one more repository; GitHub sees its size and commit times.

## D56 · The reading profile
**Chosen:** copied from the reader's X4 paper, with the section changes just made there, as the
reader's own files sealed in the data repository: sections, interests, feeds, and the files
three sections rest on. It replaces the answers given at setup.
**Not chosen:** reading the X4's repository each run (its files are plain); keeping the setup
answers.
**Accepted cost:** two copies; a change in one does not reach the other.

## D57 · Sections that rest on the reader's files
**Chosen:** the morning skill learns three: a film section chosen by `taste.md`, never a title
in `seen.md`, up to three a week; a field of the week, the first line of `fields.md` without a
week mark, given on the week's first issue as an introduction and the field's primary text,
then marked; a sport section, the clubs its line names first, with the best piece on each
club's week on the week's first issue.
**Assumed, not asked:** the X4's written primer and weekly club dossiers become found articles
(the paper writes only digests); "the week's first issue" is the first issue of the ISO week;
the X4's football data feed stays there (it needs an API key).

## D58 · Saved essays
**Chosen:** the essays the reader had saved on the X4 go into the inbox and arrive under Saved
in the first cloud issue.

## D59 · Feeds
**Chosen:** all of the X4's feeds.
**Accepted cost:** more to read each morning. The paper ignores the X4's `topic` and
`only_topic` keys, so a mixed feed brings any two new entries, and Claude leaves out what fits
no section.

## Conflict to settle
A section line asks for foreign local reporting "translated whole". The paper never translates
an article whole (that republishes it); a digest gives what it reports and argues with key
lines translated, which is what the reader's interests ask for. The digest rule applies until
the reader says otherwise.

## D60 · The run's environment and model
**Chosen:** a cloud environment of the paper's own ("morning-paper": network Full, variable
PAPER_RUN_KEY), and Opus 5.5 writing.
**Not chosen:** the Default or x4 environment (their other sessions could read the run key);
Sonnet 5.5.
**Accepted cost:** more of the plan each morning. The schedule is in UTC (04:07, 05:07 in
Budapest in winter); from summer time it runs at 06:07 local unless moved.

## The first cloud run

**D61.** The cleanup commit is pushed, and the history is left alone. The details that e4c5cd9 made public stay in the old commits. They are interests, not secrets, and rewriting the history would break every clone and the routine's checkout.

**D62.** The first cloud run (fired by hand on 2026-11-19) worked from start to finish in 6.4 minutes. It opened 9 sealed files, fetched the feed, wrote 20 pieces, 4 saved links and 3 games, and passed the publish check on its second try. It then pushed one commit to the data repository. One feed outlet refused it with a 403, and a few sites refused the article reader. It picked other sources for those.

## Step 2: the reader page

Checked 2026-11-19: a browser rechecks a page's code for updates at least daily, and the page cannot
refuse its own replacement (W3C ServiceWorker issue threads, 2018 to 2026), so D53's pinning cannot
be built as a page. GitHub Pages serves only public repositories on a free account. Face ID
unlocking for web pages (WebAuthn PRF) works from iOS 18.4, with reported failures in some flows.

## D63 · Where the page's code lives (revises D53)
**Chosen:** its own small public repository, served by GitHub Pages and never given to the
cloud run. The code is written in morning-paper's `reader/` folder; it reaches the page only
when the reader copies it over and merges.
**Not chosen:** morning-paper's own Pages (a run that can push there could rewrite the page and
take the record key, undoing D46); morning-paper's Pages with a check that warns when the code
changes (an attacker's update replaces the check within a day).
**Accepted cost:** one more repository, and a manual step for each update.

## D64 · Article text
**Chosen:** the run extracts each piece's text and seals it in the data repository, kept 30
days; older pieces open at the outlet.
**Not chosen:** headline, lead and a link only (no reader view, nothing for highlights to attach
to); keeping texts forever (about 70 MB a year, all downloaded by each run); the latest issue only.
**Accepted cost:** about 6 MB of texts in the repository. A piece whose site refuses the run has
no text either, and opens at its outlet, as the local reader did.

## D65 · The key on the phone
**Chosen:** the recovery code typed once; the phone keeps the run key, which the browser will not
export, in the page's storage under the phone's passcode encryption (as D39). The offline copy
stays sealed and is opened as it is shown.
**Not chosen:** Face ID on each open (iOS 18.4 and later, unreliable in reports); typing the code
each morning.
**Accepted cost:** whoever holds the unlocked phone can read the paper. The sealed offline copy
adds little, since its key sits beside it.

## D66 · What step 2 covers
**Chosen:** reading only: the issue, the reader view, digests, past issues, the latest issue
offline. Nothing done on the phone is recorded until step 3.
**Not chosen:** games now, kept on the phone until step 3.
**Accepted cost:** the learner hears nothing from the phone until step 3.

## D67 · The phone's GitHub token
**Chosen:** read only, for the data repository alone.
**Not chosen:** read and write now.
**Accepted cost:** a second token at step 3.

## D68 · Since you left
**Chosen:** left out until step 3, which knows what the reader last read. Running stories show
only as pieces in their sections.

## D69 · What Claude's GitHub app reaches
**Chosen:** the reader limits it to morning-paper and the data repository, so the page's
repository is out of a run's reach whatever the run does. This is the reader's step: it is a
GitHub setting.
**Not chosen:** leaving it, and trusting my unconfirmed reading that a run pushes only to the
repositories its routine lists.
**Accepted cost:** other Claude sessions lose the reader's other repositories until they are
added back.

## Step 2 as built

`src/paper/edition.py` builds each day's edition when the cloud run publishes: a front page and one
file a piece, sealed by `cloud pack` like the rest. `reader/` is the page: plain files, no build.

**Assumed, not asked:** pieces keep the issue file's order within each section, since the local
server's reordering reads the record (step 3). Article HTML is cut down on the phone to a short list
of tags with no attributes, and the page's policy runs no script but its own: an outlet's text sits on
the same page as the key, so it must not be able to act. Opened on localhost, the page reads a test
copy from its own server in place of GitHub.

**Checked (2026-11-19), in a browser against a fake paper-data on localhost:** a wrong code is
refused at setup; the issue, a digest and a past issue open; four of the first run's real articles,
extracted live, come through as plain paragraphs and lists; a poisoned article loses its script,
image, style, handler and link; a piece past 30 days opens at its outlet; with the server stopped,
the page and the latest issue open from the phone's sealed copy, and an older issue says there is no
connection. GitHub's API answers a page from another site with the token and version headers the page
sends (a preflight to api.github.com). **Not yet checked:** a real iPhone, GitHub Pages, and a
publish in a real cloud run.

## Step 3: the record on the devices

Checked 2026-11-19: the Mac has no reading record yet (no reads or marks in `~/paper`), so nothing
moves over. The phone kept only the run key at step 2, so the recovery code is typed once more for
the record key.

## D70 · The order of step 3
**Chosen:** two parts. First the record and the brief: seen, opened, finished, keep and the Kept
page, highlights and questions with their answers, "less of this" and the why line, and the brief
the run reads. Then cards, games, Since you left, and Settings with Save a link.
**Not chosen:** all at once.
**Accepted cost:** cards, games and Since you left wait for the second part.

## D71 · When the phone writes
**Chosen:** on leaving each piece, and whenever the page goes to the background; what was done
offline waits on the phone and goes at the next write that reaches GitHub.
**Not chosen:** on every action (a timed trace of every tap at GitHub); on the next open (the last
reading of a day misses the next morning's brief).
**Accepted cost:** GitHub sees roughly when each piece was finished, and a few commits a day.

## D72 · What the record keeps
**Chosen:** the same events as the Mac: seen, opened, reading time, a headline on screen long
enough, kept, marks, games, "less of this", card reviews; sealed whole with the record key.
**Not chosen:** leaving out reading time and headlines on screen.
**Accepted cost:** the record holds a fine-grained account of reading, readable only on the
reader's devices.

## D73 · The Mac's local server
**Chosen:** retired when step 3 ends; the Mac then opens the same page as the phone.
**Not chosen:** now; keeping it as a fallback.
**Accepted cost:** until then the local server does not see what is done on the phone.

## D74 · The Kept page
**Chosen:** with Keep, in step 3's first part.

## D75 · Settings and Save a link
**Chosen:** on the page, in step 3's second part; what they write is sealed with the run key, since
the run reads it. Until then, changed through Claude.
**Not chosen:** through Claude only; Save a link alone on the page.


## D76 · What the phone writes
**Chosen:** the record in one file per device and week, and in the brief only the marks of the last
14 days.
**Not chosen:** a file a month and every live mark (a guessed 0.5 GB a year, since each write saves
the whole file again and git cannot shrink sealed files); a file a month with recent marks only
(a guessed 220 MB a year).
**Accepted cost:** another device reads about 52 files a year from each device; a mark the run has
not answered within 14 days is dropped, which happens only if runs fail for two weeks. The guess
assumes about 45 events and 10 writes a day at the 115 bytes an event measured.

## D77 · The try when its topic has nothing strong
**Chosen:** both draws give `tries`, the topics from least evidence up, and the morning skill takes
the next one in it.
**Not chosen:** no fallback in the cloud; the counts in the brief (against D47).
**Accepted cost:** the run sees which topics the record is thinnest on, as an order without numbers.

## D78 · D43 retired
**Chosen:** an event keeps the phone's clock as it happened, with no clamp.
**Not chosen:** a device clamping another's future-dated events when it reads them.
**Accepted cost:** a phone with a wrong clock misdates its events, and the learner weighs them so.

## D79 · What the Kept page lists
**Chosen:** what the reader pressed Keep on, and saved links.
**Not chosen:** marked pieces too.
**Accepted cost:** a highlighted piece not kept is found only through its issue, though the
learner counts it as kept.

## Step 3's first part as built

The page keeps the reader's events on the phone. On leaving a piece or the page it writes this
week's file, `record/<device>/<Monday>.jsonl`, sealed with the record key, then `home/brief.json`,
sealed with the run key. `reader/learn.js` weighs the record as `topics.py` does, and
`src/paper/brief.py` turns the brief into the `paper context` the morning skill already reads.

**Assumed, not asked:**
- The brief holds the next issue's topic draw, the marks of D76 with their text, and the pieces
  opened in the last 14 days. No reading times, no counts (D47).
- The brief comes from every device's record and is written by whichever device wrote last.
- A visit to a piece is one read event, updated while the reader stays; the Mac logs one per
  heartbeat. The learner reads only total time and the furthest point, so both weigh alike.
- A week stays marked as unwritten until GitHub takes it, so a failed write, a reload, or iOS
  closing the page mid-write sends it again next time.
- When the token cannot write (GitHub answers 403 or 404), the issue page says so, and what was
  done waits on the phone.

**Noticed, not changed:** reading after midnight and before the morning run does not steer that
morning's order, since the draw counts what happened before the issue's day began. The Mac works
the same way.

**Checked (2026-11-20), in a browser against a fake paper-data on localhost:** setup derives both
keys; a phone set up at step 2 asks for a token that can write and the code once more. The front
page shows the answer to a question asked on another device. A why line, "less of this" and its
undo, Keep, the Kept page, and a highlight all work. Leaving a piece wrote the record and the
brief, and Python opened both: this phone's events, the other device's file untouched, both
devices' marks in the brief. A refused write showed the note and went at the next load; a write
GitHub kept turning back stayed marked. A new issue published while the page was open got its why
lines without a reload. The run's pack leaves `brief.json.sealed` alone when unchanged, so a phone
writing during a run cannot collide with it. Python's and the page's evidence, estimates and why
lines match on the same events (a test). The page writes and reads week files.
**Not yet checked:** a real iPhone, GitHub taking writes from a token that can write, and a cloud
run reading a brief.

## Step 3's second part

## D80 · Its order
**Chosen:** two rounds. First cards and running stories (Since you left); then games, Settings and
Save a link.
**Not chosen:** all four at once; Settings first.
**Accepted cost:** until the second round, settings and saved links go through Claude, and the run
writes no games.

## D81 · Card scheduling on the phone
**Chosen:** the standard FSRS scheduler with its default parameters. D31's fit to the reader's own
reviews is paused until there are enough reviews for a fit to beat the defaults.
**Not chosen:** fitting on the phone now (a WebAssembly optimizer of about a megabyte, and a page
policy that allows WebAssembly); the run fitting from review history in the brief (against D47).
**Accepted cost:** D31 waits, likely months.

## D82 · What the brief adds
**Chosen:** decisions and answers: the finished pieces still to card, each game's pick or skip, the
crossword words left unsolved, and the day the reader left each running story. No times, no counts.
**Not chosen:** card counts as well (against D47); only the pieces to card.
**Accepted cost:** the run's report no longer says how many cards were reviewed in the week.

## D83 · Where a bad settings edit is caught
**Chosen:** on the phone, before saving, with the same checks as the Mac's settings.
**Not chosen:** by the next run, which would keep the old file.
**Accepted cost:** the checks exist in Python and in the page, kept alike by a test.

## D84 · The edition's lists of pieces and cards
**Chosen:** one file a month; the run rewrites only the current month's.
**Not chosen:** one file rewritten whole each morning (a guessed 200 MB in the first year and 600 MB
in the second); one file trimmed to 180 days (the phone's learner would drift from the Mac's).
**Accepted cost:** the phone fetches one more file a month of history, kept offline after the first read.
The current month's file is still saved whole each morning: a guessed 30 MB a year (corrected from
"a few MB", said when this was asked).

## D85 · Following a story on the phone
**Chosen:** by reading: a story joins Since you left once the reader opens a piece or an update of it.
Naming stories can come with Settings in the second round.
**Not chosen:** a Follow button now; every story the run keeps.
**Accepted cost:** a story the reader cares about but has not opened on the phone shows only as
pieces in its section until they open one.

## Step 3's second part, first round, as built

The run writes the edition's lists a file a month, cards included (`edition/months/`), and keeps
`index.json` to the steered sections and the months. The page reads running stories from
`threads.jsonl` itself. It shows Since you left after the answers, a story's updates above a piece
that continues it, a story's own page, and one due card below a piece once it is finished, all as
the Mac's server does. Reviews and story catch-ups go into the record as the Mac logged them. The
brief adds `to_card` and `stories` (D82), which `paper context` passes on.

**Assumed, not asked:**
- In the cloud `cards` in `paper context` says only how many there are (D82).
- A card's piece is found through the reader's own marks; through games once games exist.
- The cloud run writes no games until the phone can play them (D80), said in the morning skill.
- Only a missing file counts as nothing. When the index, a month, the stories or another device's
  record fails to load, the page still opens from what it has, but no brief is written until they
  load: a brief from half the record would steer the run wrong.
- Next follows the front page: Since you left's pieces first, as the Mac's order.

**Checked (2026-11-20):** on the same reviews (60, random), stories and reads, the page and Python
give the same due dates to the millisecond, the same card after a piece, the same day each story
was left off, the same Since you left, and the same pieces to card (a test). In a browser against
a fake paper-data: Since you left with a story's piece moved up and a story with no piece, the
story page, the story above a piece, a card after a finished piece and its answer in the record,
and a brief carrying `to_card` and `stories`. A month file that fails to load stops the brief and not
the reading, and the next sync writes it. The new page on a copy of the real edition of the 20th
(the old index, no stories, the old labels) opens the issue, a piece and Kept, and writes a brief.
The page live before this one cannot read the new index, so the page ships before the run that
writes it. A past month's file stays as written; the one index
from before is split on the first run (a test). **Not yet checked:** a real morning run writing
cards and stories, and a real iPhone.

## Step 3's second part, second round

## D86 · Saving a link on the phone
**Chosen:** a Save a link button at the foot of the front page that reads the clipboard: Share,
Copy, open the paper, tap, then tap Safari's Paste button. (Said when asked: "iOS asks once".
Corrected: WebKit shows its Paste button on every read the page did not get from a paste itself.)
**Not chosen:** a field in Settings, as on the Mac; an iOS Shortcut in the share sheet (it opens
Safari, which likely keeps its storage apart from a home-screen page). iOS does not let a web page
take shares (as of sources from late 2025).
**Accepted cost:** a few taps more than a share target, one of them on every save.

## D87 · What Settings on the phone holds
**Chosen:** all the Mac's: sections, interests, feeds, outlets (remove only), language, and the
Less list with undo. Not pairing or the recovery code.
**Not chosen:** sections and interests only.
**Accepted cost:** the largest port of the round.

## D88 · Feeds on the phone
**Chosen:** the phone removes a feed's line or adds a name and address; every other line of
`feeds.yaml` (topics, limits, notes) stays as written.
**Not chosen:** feeds through Claude only. (The Mac's own edit rewrites the file and drops each
feed's topic; the phone does not copy that.)
**Accepted cost:** a feed added on the phone has no topic until Claude gives it one.

## D89 · Following stories by name
**Chosen:** not now; a story joins Since you left once a piece of it is opened (D85).
**Not chosen:** a Follow list in Settings.

## Step 3's second part, second round, as built

The front page carries the day's predictions and links with their answers, and Sunday's crossword
laid out by the run (its layout draws on Python's random numbers, so the phone takes it as it is).
The phone asks a piece's game before the piece, as the Mac does: the article and, for a
prediction, the outlet's own title wait for a pick or a skip; a link's story waits for the answer.
It checks the pick itself and logs it as the Mac did. The crossword page is the Mac's, with each
solved word logged. The brief adds `games`: each pick or skip, and each crossword's solved entries;
the run checks a pick against the issue and works out the words missed, so `paper context` gives
the same games as on a computer that holds the record. Month files map each game to its piece, so a
card from a missed game is never shown right after that piece. Settings (D87, D88) and Save a link
(D86) are on the page; a saved link is a file of its own in `saved/`, which `paper feed` moves into
`inbox.md`, so a save during the run never meets the run's own edit of the inbox. The cloud run
writes games again.

**Assumed, not asked:**
- The brief carries the crossword's solved entries, not the words missed: the same fact, and the
  run already has the words (D82 named the missed words).
- Forget this phone moves from the bottom bar into Settings once the edition has Settings' words.
- A refused paste or a bad link shows the browser's or the Mac's English message, as the Mac's
  Settings does.
- Letters typed in the crossword stay on the phone that typed them; solved words reach the record.
- A language change shows from the next issue, since the page's words come with the edition.
- Settings draws Forget this phone before reading the files, so it stays within reach offline; a
  write leaves the phone's saved copy current, so Settings never reopens an older file.

**Checked (2026-11-20):** tests hold the phone's settings checks to the Mac's on sections (accents,
`:`, `|`, twins, length, too many), interests, language, outlets and feeds (topics, flags and notes
kept); the brief's games give `paper context` the same games as the record; a game card maps to its
piece. In a browser against a fake paper-data: a prediction (article and title held, answer at the
end), a link (story held, answer above), the crossword (a word solved and logged), a bad and a good
section edit, interests, a feed refused, added and removed, an outlet removed, the language, Less
undone, and a saved link folded into the inbox by the run's own code. On a test copy of the real
paper: the edition of the 20th as it is opens as before; rebuilt with this code, it asks its three
predictions and Settings shows all 8 sections, 44 feeds and 38 newsrooms. **Not yet checked:** a
real iPhone (the Paste bubble, the crossword keyboard), and a real morning run writing games.

## After step 3

## D90 · What the page's redesign covers
**Chosen:** navigation and getting around, and the look overall; and daily games beyond the
three the issue asks now, of the word-game kind (the reader's example: a daily word puzzle).
**Not chosen, for now:** the front page's first screen and the reading view as their own items
(they come up in the critique if they need to).

## D91 · How the redesign runs
**Chosen:** a critique of every screen at phone width first, then a plan the reader picks from.
**Not chosen:** fixing the named parts straight away; two directions side by side.
**Accepted cost:** a round before any change.

## D92 · Step 4 and the redesign
**Chosen:** both at once: step 4 (D48, D52) in its own session, the redesign here.
**Not chosen:** the redesign first; step 4 first.
**Accepted cost:** two pieces of work in flight to review.

## D93 · The Mac's local server
**Chosen:** retired before the redesign (D73), so there is one page to redesign.
**Not chosen:** keeping it while the phone page is redesigned.

## D94 · Setting up a new reader
**Chosen:** the setup skill and the README rewritten for the cloud now, as D45 planned: the GitHub
token, the data repository, the routine and the phone page.
**Not chosen:** marking them as not working and rewriting later.
**Accepted cost:** the largest part of retiring the Mac server.

## D95 · The learner in Python
**Chosen:** kept as the reference the page's learner is tested against.
**Not chosen:** dropped, with the page's learner tested against fixed numbers.
**Accepted cost:** a change to the learner is made twice.

## D93 as built
The Mac no longer serves anything. `server.py`, `phone.py` and `tls.py` are gone with their fonts,
icon and tests, and so are `paper serve` and `paper install` (the login service). What the morning
run still needed from the server moved: the article cleaner and byline to `article.py`, the front
page's order and the stories that moved to `reading.py`. `paper publish` on the Mac now only checks
the issue; the cloud run builds the edition. The recovery code, which the Mac's Settings used to
show, comes from `paper cloud code`, run by the reader in their own terminal. The tests that read
the server's pages went with it (115 tests then, 81 now); the logic under them is still tested
directly. The QR code library left the dependencies. The setup skill and the README still describe
the Mac server until D94's rewrite.

## D96 · Who makes a new reader's repositories
**Chosen:** Claude, with the GitHub CLI when it is signed in, asking before each: the private data
repository, and the public page repository with `reader/` copied in and Pages on. Without it,
links the reader follows.
**Not chosen:** the reader by hand every time.
**Accepted cost:** two ways through one step; the CLI becomes a soft requirement.

## D97 · The end of setup
**Chosen:** setup runs the morning routine once, and the reader opens that issue on the phone.
**Not chosen:** an empty paper until the next morning.
**Accepted cost:** a full issue's worth of the plan, and about six minutes' wait.

## D98 · Stories named at setup
**Chosen:** dropped. A story joins Since you left when a piece of it is opened (D85).
**Not chosen:** a file of named stories the run reads as follows.
**Accepted cost:** the first issue has no Since you left.

## D99 · The run's time zone
**Chosen:** the reader's own, written into the schedule (`CRON_TZ=…`), so 5:07 stays 5:07 through
summer time; the first reader's routine moved too. Revises D60's note.
**Not chosen:** UTC; the reader's for new readers only.

## D94 as built
`skills/setup` sets up a reader for the cloud: the tools and files on a computer once, the recovery
code saved by the reader from `paper cloud code` in their own terminal, `paper-data` made and sealed
(with the GitHub CLI when it is signed in, D96), the environment and the GitHub app's reach as the
reader's steps, the routine in the reader's time zone (D99) with no connectors, `paper-reader` on
Pages, the phone's token as the reader's step, and one run while the phone is set up (D97). The
README says the same, and what setup leaves behind.

**Assumed, not asked:** new routines get no connectors, since the run reads untrusted pages; the
permission rules for an unattended run on the computer went with that run; `/paper:today` left the
README's commands, since on a computer it now only checks an issue.
**Not yet checked:** a setup from nothing on a new account; the Claude app's screens for the
environment; setup run a second time over an existing paper; the Windows time zone. The README's
screenshots are of the Mac's pages, to be retaken after the redesign.

## The redesign: the critique (D91)

Walked through at phone width (375 px), light and dark, on a copy of the real issue of 20 November:
every way out of the front page sits at its foot, four and a half screens down; a piece links home
only at its top; a past issue looks like today's; Settings is one page of eight screens; the
dateline takes a quarter of the first screen and the gaps between sections are tall; the why line
comes before the title; a piece opens under the outlet's title, not the headline tapped; the
Highlight bar is a see-through pill over the text; the front page never mentions the games; a
byline repeats an accented name; footnote numbers stick to words. Numbered R, since step 4 numbers
from D100.

## R1 · Getting around
**Chosen:** a slim bar at the top of every page: the date, which leads to today, then Kept and
Settings. The foot keeps Save a link and the previous day.
**Not chosen, for now:** a way home at a piece's end; past issues marked as past; Settings in parts.

## R2 · The look
**Chosen:** the date on one smaller line and tighter gaps between sections; a piece opens under the
headline the reader tapped, the outlet's own title moving into the byline; the why line under the
byline, smaller, with Less of this as a button.
**Not chosen:** a solid Highlight bar on its own (R3 replaces it).

## R3 · Highlighting
**Chosen:** select any words and the bar offers Highlight and Question; a tap still marks the whole
paragraph. The bar sits at the bottom, clear of the phone's own menu over a selection.
**Not chosen:** selection only.

## R4 · How a marked passage is kept
**Chosen:** by its words, as a paragraph is now; the page lights the first place they appear.
**Not chosen:** words plus position.
**Accepted cost:** a phrase that appears twice in a piece lights the first.

## R5 · A daily word game
**Chosen:** a five-letter guess: six tries, letters marked right, misplaced or absent, in the
paper's own look. The word is one Claude picks as central to a piece of the day's issue; solving
shows that piece. Guesses must be real words, from a freely licensed list checked before use.
**Not chosen:** a missing word from a headline; both alternating; any letters as guesses; any
common word.
**Accepted cost:** the genre's best-known mechanics; a word list shipped with the page.

## R6 · Its language
**Chosen:** the page's language; a page in Hungarian gets no five-letter game until a Hungarian list
is found and checked.
**Not chosen:** alternating by day; the piece's language; finding a Hungarian list now.

## R7 · What the game logs
**Chosen:** every guess in order, and whether it was solved.
**Not chosen:** solved and the number of tries only.
**Accepted cost:** up to six words a day in the record.

## R8 · Also in
**Chosen:** one line near the top of the front page naming the day's games, each a link; writer
names that differ only by accents merged, and footnote numbers and return links dropped by the
run's cleaner.

## Step 4

Measured on 2026-11-20 on the Mac, on the real snapshots of 17 Nov: 1,332 headlines from the
reader's 38 outlets, which the engine grouped into 1,103 stories by shared title words. To
compare models, 185 pairs of a Hungarian headline and its closest foreign one were labelled by
hand (63 the same story). The labels are mine and come from titles alone. Each model's score is
the share of same-story pairs it catches while 9 in 10 of its merges are right. multilingual-e5-base
catches 62%, e5-large 44%, its 8-bit build 43%, mpnet 32%, e5-small 16%, MiniLM and the static
model2vec model about 0. EmbeddingGemma ranked worse than chance on these titles. Overall
(AUC) e5-base and e5-large tie at 0.90 and 0.91. Only 10 of the 63 pairs had both sides inside the
60 stories `discover.mjs` hands on each day. Cloud facts (code.claude.com, cloud-environments,
read 2026-11-20): about 4 vCPU, 16 GB and 30 GB of disk a session; a setup script's result is cached about
seven days. That scheduled runs get the cache is my inference: the page says only that they use the
same environments.

## D100 · The model
**Chosen:** multilingual-e5-base (MIT, Hungarian among its languages), the full ONNX file,
1.1 GB; a day's headlines in about 25 s on the Mac.
**Not chosen:** its 8-bit build (279 MB, catches 43%, built for one family of Intel CPUs);
e5-large (2.2 GB, 77 s, no better); the small and static models (miss most cross-language
pairs).
**Accepted cost:** the largest download of the options. The cloud's speed is unmeasured.

## D101 · Replace or sit on top (settles D48's open question)
**Chosen:** on top. The engine's word groups are the building blocks, read in full (every group,
not discover's top 60), and the embeddings merge them. With no model the feed falls back to the
engine's groups, with a warning.
**Not chosen:** replacing the word matching (its precise same-language matches would become
threshold guesses); merging only inside the top 60 (misses 53 of the 63 pairs).
**Accepted cost:** Python now ranks what discover's top-60 cut used to.

## D102 · What may be merged
**Chosen:** two strict rules. Within a language, only near-identical groups (0.91 on every pair).
Across languages, a group and one in another language when each is the other's closest match
and they score 0.84 or more (17 of 18 right on 17 Nov).
**Not chosen:** across languages only (two days of one story stay apart); a looser cut that
merges a story's angles (about a third of its merges wrong, each one inflating `k`).
**Accepted cost:** a story split by its angles mostly stays split; Claude still counts it once.

## D103 · How the model reaches the run
**Chosen:** `cloud-run.sh start` downloads it into a cache folder when it is missing; one line in
the environment's setup script can put it in the seven-day cache.
**Not chosen:** the setup script alone (no model once the cache lapses); a fresh download every
run.
**Accepted cost:** a morning without the cache spends the download's time (unmeasured).

## D104 · When an entry is not new
**Chosen:** an entry of a running story restates an earlier one when they score 0.93 or more and
it brings no number or name the earlier one lacks. On 17 pairs I wrote (no real `threads.jsonl`
exists to test on), this caught 5 of 7 restatements and flagged none of 10 developments
(corrected: I said 8 and 9 when this was asked). Cosine
alone put "the MNB cut its rate" at 0.938 against "the MNB held its rate".
**Not chosen:** cosine alone; near-verbatim only (0.96, 3 of 7).
**Accepted cost:** a rewording that adds a name passes; the threshold rests on pairs I wrote.

## D105 · What happens to a restatement
**Chosen:** `paper publish` refuses it, naming both entries; Claude drops it or writes the new fact.
**Not chosen:** a warning nobody reads in the morning; a hint in the feed only.
**Accepted cost:** a wrong flag costs Claude a rewrite.

## D106 · Matching stories to threads in the feed
**Chosen:** not now; Claude matches them as before.
**Not chosen:** a `thread` hint on news stories, untested without real threads.

## D107 · The rule on language models
**Chosen:** CLAUDE.md now says the `paper` tool never calls a generative model or a model API. It
may run a local text encoder, which turns text into numbers and writes nothing.
**Not chosen:** keeping the old line and reading it narrowly.
**Accepted cost:** the line admits local models.

## D108 · What the feed remembers as reported
**Chosen:** only the 30 stories it reports. A story cut today can come back tomorrow while the feeds
still carry it, with its new coverage counted.
**Not chosen:** the top 60, as before (ranks 31 to 60 dropped for good); every group (about 1,300
URLs a day in a state file sealed whole each morning, a few MB a day of repository).
**Accepted cost:** Claude may see yesterday's runner-up again and judges whether it moved.

## Step 4 as built

`paper feed` now reads every one of the engine's claim clusters (`cluster-claims.mjs`, in place
of `discover.mjs` and its top 60). `src/paper/group.py` merges them by D102's two rules with the
encoder in `src/paper/embed.py`, and ranks by `k` as before. `paper publish` runs
`issue.restated` on the thread entries written since the last issue (D104, D105). `paper model`
downloads the encoder, pinned to one revision and checked against its hashes, into
`~/.cache/paper/models`; `cloud-run.sh start` calls it, and `cloud-run.sh model` runs it alone,
for a setup script. The morning skill says both.

**Assumed, not asked:**
- Headlines are decoded (`&apos;`, CDATA wrappers) before they are compared and shown, as they
  were when the thresholds were measured.
- Across languages, each pair of languages finds its matches on its own, then they are joined:
  a French match never takes the place of a Hungarian one.
- discover's triage points (constitutive source, readable outlets, signs of a rule or public
  money) are ported to Python, because they still break ties in `k`.
- The engine's full cluster files are not sealed into the data repository: like discovery, they
  are made again from the snapshots (0.75 to 2.9 MB a day).
- A catch-up after many days embeds at most 6,000 headlines, the strongest stories first; the
  rest are not merged, with a warning.
- With no encoder, the feed gives the engine's groups and a warning, and publish prints a note
  and publishes unchecked.
- A group's language is the language most of its sources are in.
- `start` downloads the encoder after the reader's files are open, so a failed download costs the
  merging, never the run.

**Checked (2026-11-20, on the Mac):** the encoder's vectors match the ones measured with
(cosine 1.0 on all 1,332 headlines of 17 Nov). On 17 Nov 19 of the top 30 stories are merges, 10 of them across languages, and all 10
cross-language joins are right. The Crimean bridge strike rose from k 5 to 12 and to the top, with
two Hungarian and one French account; the Hungary–Ukraine rail halt went from 4 to 8, the Iranian
dirty-bomb report from 3 to 7, the Rwanda return hubs from 3 to 7, the Serbian parliament from 2
to 6. One join inside a language was wrong: Russia's strike on Kyiv's bridges went in with
Ukraine's strike on the Crimean bridge. The encoder scores them 0.91 to 0.94, its limit, and k
gained one. A first build let a French match take the Hungarian one's place (the Crimean bridge
came out with no Hungarian source); a test now holds a story told in three languages together.
On 18 Nov the summit took in its angles (k 9 to 17). Grouping added 19 s on the 17th and 23 s on
the 18th. The restatement rule, on the 17 pairs, gave D104's counts. `paper model`
downloaded and checked both files in 47 s. 125 tests pass.
**Not yet checked:** a real cloud run: the encoder's speed on its CPUs, the download time, and
whether a routine gets the setup script's cache. Also real thread entries, which the 0.93 rests
on only through pairs I wrote.

## R9 · What the five-letter game tells the run
**Chosen:** solved or not, and in how many tries; the guess words stay on the reader's devices.
**Not chosen:** every guess; nothing.
**Accepted cost:** Claude cannot see which words tripped the reader.

## R10 · Its name
**Chosen:** Lede.
**Not chosen:** Five; Word of the day.

## R11 · Its word list
**Chosen:** ENABLE (public domain by its maintainers' README, which asks for credit), from the
enable1.txt mirror on norvig.com since Debian's package carries the documents but not the list; its
8,636 five-letter words ship with the page and the run's check, with a credit file.
**Not chosen:** SCOWL from Debian.
**Accepted cost:** obscure Scrabble words count as guesses. The mirror holds 172,819 words, 709
fewer than the README's count for its master list (I think the enable1 edition).

## The redesign as built (R1 to R11)
Every page opens with the bar: today's date, which leads to today's issue, then Kept and Settings.
On today's front page that date is the page's title. The foot holds Save a link and the days on
either side. Under the bar, one line names the day's games: Lede, the crossword, and each piece that
asks first, as Guess 1 and Guess 2; a game played is grey with a tick. A piece opens under the
headline tapped; the outlet's own title heads the byline in italics, hidden while a prediction waits.
The why line sits under the byline, with Less of this as a small button. Words selected bring up
Highlight and Question at the bottom; a tap on marked words offers Remove; a tap on a paragraph
marks the whole paragraph, as before. Lede is `#<day>/lede`: six rows of five letters, a keyboard on
the page as well as the phone's, guesses checked against `reader/lede/words.txt`, each one logged.
Black means in place, a ring means elsewhere in the word, grey means not in it. Once it is solved or
lost, the keyboard goes, and the word and its piece show. The page's cache is `shell-v4`, with the
word list in it.

**Assumed, not asked:**
- Today's bar drops the year ("Thursday 19 November"). The full dateline does not fit beside Kept
  and Settings at 375 px, even at 17 px. The tab title keeps the year, and so does a past issue's
  heading under the bar.
- A selection that runs past its paragraph keeps only the part in the first one.
- The games line's wording, "Guess" and "Tipp", and "Not in the word list." are drafted by Claude,
  not decided. So are the rules for Claude picking a Lede word in `skills/today`.
- A Lede guess made offline, before the word list was ever saved, is taken as any five letters.

**Checked:** at 375 px, in light and dark, on a test paper sealed as the run seals it. Covered: the
front page, a past issue, a piece with the outlet's own title, the prediction holding that title
back, the why line, a selection marked and restored after a reload, a selection across an italic
word, Remove, and a Lede played, solved, lost after six tries, and restored; the games line ticks Lede only once it is over. An install made as `install.sh` makes it finds its own copy of the word list. The tests cover the run's side: the check,
the edition, the brief's tries, and the phone's brief matching the record. The phone's scoring has a test of its own, with repeated letters. Selection marking has none: it was walked, not tested unattended.

**Not yet checked:** selection on a real iPhone, where the phone's own menu competes with the bar
and a finger on the bar may drop the selection (the bar now stays until the tap ends);
the page in Hungarian; a past issue without the new fields on the real data.

## R12 · The date in today's bar
**Chosen:** "Thursday 19 November", no year, on one line beside Kept and Settings.
**Not chosen:** the full date on a line of its own; the full date with smaller links.
**Accepted cost:** today's page never shows the year on screen; the tab title and past issues do.

## R13 · A selection across paragraphs
**Chosen:** the mark keeps the part in the first paragraph.
**Not chosen:** one mark per paragraph touched.
**Accepted cost:** the rest of a long selection is dropped without a word.

## R14 · The games line's words
**Chosen:** Lede, Crossword, then Guess 1, Guess 2 (Tipp in Hungarian) for the pieces that ask first.
**Not chosen:** the pieces' headlines; Predict and Link.

## Gap 1: setup never run from nothing
Every name setup uses is already your real paper's on this Mac and these accounts: `~/paper`,
`~/paper-data`, the repos `paper-data` and `paper-reader`, the `morning-paper` environment, the
routine "Morning paper". A test run here as you would land on them. With `PAPER_RECOVERY_CODE` set,
the paper never writes the keychain, and `vault.ensure` never replaces a stored code. CI already
runs the install and a new home on Ubuntu, Windows and macOS. What never ran is everything after.

## D109 · How real the test is
**Chosen:** staged. First Claude checks the setup skill and README against the code, and runs the
local steps twice in a sandbox (a test code, a temporary home, a local repository). Then you walk it
once for real, with a checklist.
**Not chosen:** the full walk now; a friend setting it up; the sandbox only.
**Accepted cost:** the sandbox alone does not close the gap.

## D110 · The routine in the real walk
**Chosen:** the walk stops before the routine; that step is checked by reading what it would send.
**Not chosen:** a renamed test routine, deleted afterwards.
**Accepted cost:** making the routine stays unproven.

## D111 · The GitHub account for the real walk
**Chosen:** yours, with renamed repositories.
**Not chosen:** a second account.
**Accepted cost:** not the script as written; test repositories sit beside the real `paper-data`.
Which GitHub path the walk takes is D117.

## D112 · Windows
**Chosen:** its time-zone step stays named as unchecked until someone on Windows sets it up.
**Not chosen:** dropping Windows from setup's promises for now.

## D113 · Where the real walk runs
**Chosen:** a new macOS user, with its own home and keychain.
**Not chosen:** another Mac; your own user with PAPER_HOME and a test code.
**Why it matters:** as your own user, setup would find your real recovery code and reuse it, and its
step 3 would rewrite `outlets.json`, `sections.md`, `interests.md` and `paper.yaml` in your real
`~/paper`.

## Gap 1, stage one as built
**Checked alone, 20 Nov:**
- The setup skill and the README read against the code.
- In a sandbox, with a test code, a temporary home and a local bare repository: `paper init`, step
  3's files, `paper check`, and step 4's pack and push. `install.sh` did not run (CI covers it), nor
  did `gh repo create`. `init` wrote the six files; all 23 World outlets and 3 feeds answered.
  `init` and `pack` repeat cleanly when nothing changed in between. That is not a rerun; see below.
- The routine step 5 would create matches the working "Morning paper" routine in every field:
  prompt, model, tools, schedule, sources, no connectors. That routine delivered on 20 Nov.
- `${CLAUDE_PLUGIN_ROOT}` is filled in inside a plugin's SKILL.md (Claude Code's skills docs), so
  step 1's line resolves.

**Broke, fixed:** step 6 turned Pages on with `gh api repos/{owner}/…` in a command of its own. `gh`
fills `{owner}` from the folder's git remote, and outside the clone it fails ("unable to expand
placeholder"). It now runs `cd ~/paper-reader &&` first. Checked with a read through the same
placeholder; the POST itself has not run.

**Found, not fixed:**
- The sandbox pack also sealed the engine's own record from this checkout (public gazette text).
  A stranger's first pack would not have it. Harmless; noted so it isn't read as a leak.

**Not run here:** the cloud run's start and finish. The run is always Linux, which CI covers, and
running them here would rebuild this checkout's environment without its dev tools.

**Still open, for the real walk** (`decisions/2026-11-20-setup-walk.md`):
- the install line in the app;
- the app's environment screens;
- the GitHub app's reach;
- the path without the GitHub CLI;
- Pages from nothing;
- a fresh keychain code.

Making the routine stays unproven (D110), and so does Windows (D112).

## Gap 1: what a second setup did
A real rerun meets a data repository days ahead of the computer: the cloud has written issues, the
phone has changed Settings. In the sandbox, setup run again over such a repository (step 3's
files, then step 4's pack) deleted the issue from the repository and wrote the computer's old
`sections.md` over the phone's. Git history kept both, but the phone reads only the latest state.
That was D94's "setup run a second time", and it failed.

Every GitHub Pages site on an account is served from `<them>.github.io`, and the phone page keeps
its token and keys in that address's storage. A script on any other Pages site of the account could
read the token and use the keys. Today `paper-reader` is the account's only Pages site. This widens
D63: whoever can change any page on that address can take the record.

## D114 · A second setup
**Chosen:** open the paper first. When `paper-data` exists, setup restores the reader's code (if
the computer made a new one), clones and unpacks before anything, skips the questions and the
files, and does only what is missing.
**Not chosen:** refusing a second setup.
**Accepted cost:** a longer setup skill.

## D115 · Pack deletes only when told
**Chosen:** `paper cloud pack` refuses when the repository has files the folder lacks, unless given
`--prune`. Only the morning run's finish passes it, for the 30-day texts and folded saved links.
**Not chosen:** no guard.
**Decided by Claude, not asked:** pack also never seals over a file its key cannot open. Setup on a
new computer makes a new code, and the old pack sealed every file again with it, which locks the
phone out. Nothing needs re-keying: there is no key rotation, and the run and the phone seal with
one key. The alternative was to leave it to setup's order of steps.

## D116 · The shared address
**Chosen:** a rule, said by setup and the README: no other Pages site on the account that holds the
page. Setup lists the account's Pages sites and asks before going on when there is one.
**Not chosen:** an address of its own (a GitHub organization); accepting it.
**Accepted cost:** nothing enforces it, and that account cannot host another site.

## D117 · The walk's GitHub path
**Chosen:** with the `gh` CLI signed in: setup's main path, where the Pages break was.
**Not chosen:** without the CLI; both.
**Accepted cost:** the github.com/new path stays unwalked.

**Checked, 20 Nov:** in the sandbox, a stale computer's pack is refused and writes nothing. The
repair path opens the paper, with the issue and the phone's edit, and a pack after it changes
nothing. A new computer with a new code stops at the first file. Two new tests cover the guard; 102
pass.
