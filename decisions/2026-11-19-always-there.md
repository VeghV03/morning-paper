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

## D43 · The time of what was done offline
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

**Checked in a browser (2026-11-19), against a fake paper-data on localhost:** a wrong code is
refused at setup; the issue, a digest, an article and a past issue open; a poisoned article loses its
script, image, style, handler and link; with the server stopped, the page and the latest issue open
from the phone's own copy. **Not yet checked:** a real iPhone, GitHub Pages, and GitHub's own API.
