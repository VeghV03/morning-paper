# morning_paper_: brand and roadmap

Asked on 2026-11-20 as 30 questions in eight rounds, answered by Valentin. IDs BR1 to BR30. The
art direction starts from four references he gave: The London Letter's reels (two links:
black-and-white grain, heavy grotesque capitals one word at a time, architecture), a Photoshop
poster tutorial by anaellecdesign (displacement, yellow duotone on black, housing blocks), and a
DaVinci Resolve plugin shown by studiopaperwolf (newsprint, halftone, dither, riso looks). Claude
saw a few muted frames of each, not the full reels.

## Round 1: premises

## BR1 · Who the brand is for
**Chosen:** strangers, after 20 Dec. Built now, shown once the 30 days pass; it is the face of the
stranger-setup stage.
**Not chosen:** public now (a channel and waitlist during the 30 days, revising D33); Claude users
only (the directory, README and install page).
**Accepted cost:** no outside audience before January.

## BR2 · What the recommendation engine recommends (revises U8's framing, keeps MP-B3)
**Chosen:** beyond the news only: essays, long reads, saved links and topics for the steered
sections. News stays with the editor's tests and `k`.
**Not chosen:** news too (revises MP-B3 and MP-B4); the reader's own sources only.
**Accepted cost:** the news never adapts to the reader.

## BR3 · Where the new look lives
**Chosen:** around the reading: masthead, opening screen, icon, landing page, social, share cards.
The reading itself stays ink and one serif (D4, D9 to D12 stand).
**Not chosen:** everywhere; grotesque caps for headlines only.
**Accepted cost:** two looks that must read as one brand.

## BR4 · Changes during the 30 days
**Chosen:** no freeze. What ships during 21 Nov to 20 Dec ships to the live run.
**Not chosen:** freeze both; freeze the look only.
**Accepted cost:** the pass or fail on 20 Dec says whether the paper as it changed held up, not
whether the 21 Nov paper did. A change that drops opens cannot be told apart from a bad week.

## Round 2: the references

## BR5 · From The London Letter
**Chosen:** the photography (black and white, grain, scan lines, architecture) and the pacing (one
claim per beat).
**Not chosen:** its heavy grotesque capitals; its finance-and-power tone.
**Accepted cost:** every image needs treating; pacing implies motion somewhere.

## BR6 · From the anaellecdesign poster
**Chosen:** a daily poster: each issue gets one cover image.
**Not chosen:** yellow on black as the palette, the housing blocks as subject, displacement.
**Accepted cost:** a picture made every morning.

## BR7 · From the studiopaperwolf plugin
**Chosen:** nothing; it was a technique demo.
**Not chosen:** halftone and dither, newsprint grain, riso red.

## BR8 · Colour on the brand surfaces
**Chosen:** black, white, grey and one yellow. Yellow marks and fills; it is never text on white.
**Not chosen:** strict monochrome; mono and blue; a yellow and black duotone.
**Accepted cost:** one colour to hold beside a monochrome reading page. Claude's claim that one
spot colour ties both looks together is a guess.

## Round 3: name and image

## BR9 · How far the name goes
**Chosen:** every surface a person sees: masthead, page title, icon, README, landing page,
directory listing. The tool, plugin id and commands stay `paper`.
**Not chosen:** a full rename (breaks installs, reruns the stranger test); masthead only.
**Accepted cost:** the name you type differs from the name you read. Unverified: whether a plugin
name may hold an underscore.

## BR10 · The underscore
**Chosen:** a cursor: the paper is being written for you. A monospace lowercase wordmark; the
underscore blinks in motion and sits still in print.
**Not chosen:** decoration; a blank filled with the reader's name.
**Accepted cost:** a monospace face beside the reading serif.

## BR11 · Where the photography comes from
**Chosen:** public-domain and CC0 archives (the Met, Cleveland, Art Institute, Wikimedia),
treated with grain and scan lines.
**Not chosen:** own photos; licensed news photos; no photos.
**Accepted cost:** archive pictures match the day's news loosely, never literally.

## BR12 · How the poster is made (D107 stands)
**Chosen:** composed by code: Claude picks the lead claim and an archive photo, code lays them out.
**Not chosen:** an image model (revises D107); type alone.
**Accepted cost:** one template, which can feel repetitive.

## Round 4: public face, poster, motion, voice

## BR13 · What the brand publishes after 20 Dec
**Chosen:** a handful of product reels showing a morning with the paper, in the London Letter's
pacing.
**Not chosen:** a daily public house edition (a second product); readers sharing posters; nothing.
**Accepted cost:** no daily channel; reach grows slowly.

## BR14 · Where the poster appears (bends M3, M5: one more screen before the issue)
**Chosen:** the issue's cover, the first screen before the front page; one tap passes it.
**Not chosen:** a header on the front page; the archive and sharing only.
**Accepted cost:** one more tap each morning, against "one thing on screen".

## BR15 · Where the cursor moves
**Chosen:** only while the issue is being written; it stops when the issue lands.
**Not chosen:** a type-on at every opening; motion in marketing only.
**Accepted cost:** most mornings nobody sees it blink.

## BR16 · Voice
**Chosen:** dry and exact, a wire editor: short declaratives, numbers where they exist, no hype.
**Not chosen:** warm and personal; the London Letter's money-and-power register.
**Accepted cost:** reads cool to some strangers.

## Round 5: the news engine

## BR17 · The failure hunted first
**Chosen:** missing a big story (recall).
**Not chosen:** filler and repeats; one-sided coverage; lateness.
**Accepted cost:** more candidates reach Claude, so filler risk rises; MP-B3's "no filler" is held
by the editor, not the engine.

## BR18 · How the engine is measured
**Chosen:** against an outside public record of what happened (for example Wikipedia's Current
Events portal), scored by code in CI on saved snapshots. No reading data.
**Not chosen:** Valentin labelling a day a week; both.
**Accepted cost:** the reference is English-centred and thin on Hungary.

## BR19 · Where the next gain comes from
**Chosen:** primary sources as signals in their own right: gazettes, court rulings, central bank
and EU documents.
**Not chosen:** more outlets; looser merging.
**Accepted cost:** source work per country; documents are dry to rank.

## BR20 · The editor's tests (decides MP-B4's open item; not built yet)
**Chosen:** written into skills/today as rules Claude applies (life, power, reach); `k` is a hint.
**Not chosen:** scored by code; `k` as the rank.
**Accepted cost:** hard to test in CI; varies run to run.

## Round 6: engine ownership, threads, cadence, presets

## BR21 · Who owns the engine
**Chosen:** one engine shared with LatoTér; gains land there and reach both products.
**Not chosen:** a fork; a rewrite in Python.
**Accepted cost:** every change must suit both products.

## BR22 · Matching stories to threads (D106)
**Chosen:** built after two weeks of real `threads.jsonl` entries, tested on them.
**Not chosen:** now, on pairs Claude writes; never.
**Accepted cost:** until then Claude matches by hand and may miss one.

## BR23 · Issues a day
**Chosen:** one morning issue.
**Not chosen:** a morning issue plus an afternoon update; live.
**Accepted cost:** news after 05:00 waits a day.

## BR24 · Outlets for strangers (extends D33's presets)
**Chosen:** `/paper:setup` asks the country and assembles outlets from a vetted list.
**Not chosen:** three more hand-built presets; World only.
**Accepted cost:** one vetted list per country, thin for small countries.

## Round 7: the recommendation engine

## BR25 · Where beyond-news candidates come from
**Chosen:** the reader's own sources plus a vetted pool of long-form feeds per topic that
morning_paper_ maintains.
**Not chosen:** open web search in the run (more untrusted pages, D47); the reader's sources only.
**Accepted cost:** the pool needs keeping, and its taste becomes the brand's.

## BR26 · What the learner learns about (builds on D25 to D30; touches D49, D95)
**Chosen:** topics as built, then piece-level similarity computed on the phone from vectors the run
ships with each piece. The brief stays decisions only (D49).
**Not chosen:** topics only; pieces only (the why line loses its words).
**Accepted cost:** a larger edition and more work on the phone.

## BR27 · Serendipity (bends U22, D27: worth first)
**Chosen:** one piece a week from outside the reader's topics, labelled as such.
**Not chosen:** as built (Thompson's uncertainty and one try a section); one a day.
**Accepted cost:** a weak week shows a weak piece, against "worth first".

## BR28 · Cold start
**Chosen:** setup's three answers weight the topics; learning starts on day one (N48).
**Not chosen:** importing reading history; an editor-only first week.
**Accepted cost:** the first week is generic.

## Round 8: measuring and order

## BR29 · How the recommendation engine is measured
**Chosen:** a replay of the learner against the reader's own record, run in their own terminal
like `paper days`; it says better or worse, and the reader reports it.
**Not chosen:** a monthly verdict; simulated readers in CI.
**Accepted cost:** tuning rests on what the reader chooses to report.

## BR30 · Order
**Chosen:** engines until 20 Dec, brand assets built alongside; January the brand on the page and
the stranger test; February the directory and the reels.
**Not chosen:** brand first; strangers first.
**Accepted cost:** strangers wait until January.

## Follow-ups from the critique (asked the same day)

Checked before logging: English Wikipedia's Current Events portal keeps one page a day as plain
wikitext, nested by topic, each item with its source link (fetched for 17 Nov 2026), so code can
score against it. On Hungarian Wikipedia no daily equivalent was found. Telex keeps a
"Legfontosabb" list (telex.hu/legfontosabb) and Economx publishes a "napi összefoglaló"; neither is
confirmed as a daily, machine-readable roundup. Vector size is arithmetic, not measured:
multilingual-e5-base gives 768 numbers a piece, about 0.8 KB at 8 bits, 1.5 KB at 16.

## BR31 · Recall for Hungary (extends BR18)
**Chosen:** a Hungarian outlet's daily roundup as the second reference.
**Not chosen:** Valentin labelling a Hungarian day a week; World only.
**Accepted cost:** one outlet's judgement stands in for the truth. If that outlet is also among the
reader's outlets, the check partly grades the engine against its own input.

## BR32 · The brand on Valentin's phone (revises T6; resolves BR1 against BR4)
**Chosen:** all of it ships before 20 Dec, and a day counts as opened when the cover is shown.
**Not chosen:** after 20 Dec; the wordmark now and the cover later.
**Accepted cost:** T6's definition changes inside the window. Days before the cover ships count
the front page; days after count the cover.

## BR33 · The redesign and a page test
**Chosen:** before any engine item: push the redesign, copy `reader/` to paper-reader, add a test
that walks the page in a real browser.
**Not chosen:** push now and test in January; hold the redesign to January.
**Accepted cost:** engine work starts a few days later.
**Found after:** another session had already pushed the redesign (5624b94) and put it live on
paper-reader (3401135); what is left of BR33 is the browser test.

## BR34 · What goes live during the count
**Chosen:** every Phase 1 item except piece vectors (BR26), which wait until after 20 Dec.
**Not chosen:** only skill changes; all eight.
**Accepted cost:** steering stays topic-level for a month.

## BR35 · A specimen before the brand ships
**Chosen:** one page first: the wordmark and one poster, at phone size, in light and dark.
BR5 to BR12 count as settled only once Valentin approves it.
**Not chosen:** build into the page and adjust.
**Accepted cost:** a day or two before the brand reaches the phone.

## BR36 · The news engine's target
**Chosen:** the recall check runs for a week, then Valentin sets the target with the baseline in
front of him.
**Not chosen:** 9 in 10 now; no number.
**Accepted cost:** no target until early December.

## BR37 · A grim lead
**Chosen:** no photo that day; the claim alone, set large.
**Not chosen:** abstract photos always; Claude's judgement alone.
**Accepted cost:** Claude decides what is grim; the cover changes character on those days.

## BR38 · The vetted pool
**Chosen:** a file in the repo, drafted by Claude from the reader's feeds; Claude proposes
additions, Valentin approves.
**Not chosen:** Claude edits and Valentin vetoes; readers propose by pull request.
**Accepted cost:** a few minutes of Valentin's a month.

## Left to Claude (engineering, no product consequence)
How the phone learns the run is still writing (BR15), and where the recall check's snapshots live.

## Still Claude's proposals, not decided
Hungary and the EU first for primary sources; the order inside each phase; the monospace face and
the exact yellow (to be shown in the specimen, BR35); which Hungarian roundup serves BR31.

## The specimen (BR35), approved the same day

Canvas: https://claude.ai/artifact/Fih7teksJGsGXMXQYQZ3AC (private). The wordmark in light and dark,
and the cover in light and dark at 390 × 844. Photo: "First Bank of the United States,
Philadelphia", Frederick DeBourg Richards, 1859, Cleveland Museum of Art, CC0. It is cropped to the
picture inside the plate, turned grey, given auto-contrast and +25% contrast, every third row
darkened by 10% for the scan lines, and Gaussian grain (σ 14) added. The dark cover dims it to 86%.
The lead claim comes from Wikipedia's Current Events page for 19 Nov 2026 (JODI figures). The cursor
is the final underscore in ink on a yellow block, so the yellow is a fill, never text (BR8).

## BR39 · The wordmark's face
**Chosen:** IBM Plex Mono, 500.
**Not chosen:** JetBrains Mono; Space Mono.
**Accepted cost:** common in tech branding.

## BR40 · The yellow
**Chosen:** #FFD400.
**Not chosen:** #F2C200; #FFE14D.
**Accepted cost:** close to warning signage.

## BR41 · The cover
**Chosen:** approved as drawn: wordmark and date on top, the photo full width, the lead claim
below it in the reading serif (Source Serif, as Paper Serif). BR5 to BR12 are settled.
**Not chosen:** the claim set over the photo; a smaller photo.

## BR33 as built

`tests/test_page.py` builds an issue with `edition.build`, seals it with `cloud.pack` under the test
code, and serves the page with a local stand-in for GitHub's contents API (app.js already asks
localhost on localhost). It opens the page in headless Chrome, which `tests/walk.mjs` drives over the
DevTools protocol using Node's own WebSocket, so nothing new is installed. The walk fills the setup
form, then opens the front page, two pieces, a saved link, done, the crossword, Lede, Kept and
Settings at 375 px. It fails on any exception the page throws, any console error, any error the
page catches and prints, and any expected text that is missing. It runs in the unit tests on each CI
system where Chrome and Node are found, and is skipped elsewhere; it takes about 4 s.
**Checked:** an edition with its `labels` removed (the class of the 20 Nov crash) fails it with
"Cannot read properties of undefined (reading 'since')"; the real edition passes. 103 tests pass.
**Decided without asking (engineering):** Chrome over the protocol rather than Playwright (no new
dependency; Playwright would add a browser download per CI system). The piece whose outlet refused
its text is not walked: the page sends the reader to the outlet by design.
**Not covered:** typing in the crossword, Paste, rating a card, offline reading, a real iPhone,
Android, the page in Hungarian.
