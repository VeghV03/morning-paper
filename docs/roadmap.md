# morning_paper_ roadmap

From BR1 to BR38 (`decisions/2026-11-20-brand-roadmap.md`), 20 Nov 2026. The bar
(`~/claude-brain/bars/morning-paper.md`) defines ready; this file sets the order.

The product is two engines under one brand. The news engine finds what happened and how widely
it was reported. The recommendation engine picks everything beyond the news: essays, long reads,
saved links and topics. It never steers the news (MP-B3, BR2). The brand sits around the reading
and never inside it (BR3). Everything below ships to the live run while the 30 days are counted
(BR4), except where it says otherwise.

## First, this week

1. Done 20 Nov: `tests/test_page.py` walks the phone page in headless Chrome on an edition built
   and sealed as the run does it (BR33). The redesign was already pushed (5624b94) and live on
   paper-reader (3401135).
2. Done 20 Nov: the specimen of the wordmark and cover is approved (BR35, BR39 to BR41): IBM Plex
   Mono, #FFD400, the claim under the photo.

## Phase 1 · To 20 Dec

**Brand, once the specimen is approved** (BR32)
3. The wordmark is `morning_paper_` in lowercase monospace, the underscore a cursor that blinks
   only while the issue is being written. The palette is black, white, grey and one yellow (BR8,
   BR10, BR15).
4. Each morning the poster becomes the issue's cover. Code composes it from the lead claim and a
   public-domain archive photo, treated with grain and scan lines. On a grim day it carries the
   claim alone (BR11, BR12, BR14, BR37). From the day the cover ships, a day counts as opened
   when the cover is shown (T6 revised).
5. The name goes on every surface a person sees. The tool, plugin and commands stay `paper`
   (BR9).

**News engine** (shared with LatoTér, BR21)
6. The editor's tests (life, power, reach) go into `skills/today`, with `k` as a hint (BR20). The
   README's "independent outlets decide" is reworded to match.
7. A recall check in CI on saved snapshots. Two references score it: Wikipedia's Current Events
   pages for the world, and a Hungarian outlet's daily roundup for Hungary (BR18, BR31). After a
   week of baseline you set the target (BR36). From then on, each engine change is judged by
   whether it moves recall toward that target.
8. Primary sources become signals of their own: gazettes, court rulings, central bank and EU
   documents (BR19).
9. From about 5 Dec, once two weeks of real threads exist, stories are matched to threads (BR22).

**Recommendation engine**
10. A vetted pool of long-form feeds per topic, kept as a file in the repo. Claude drafts it and
    you approve (BR25, BR38).
11. One piece a week from outside your topics. The why line says so (BR27).
12. A replay command run in your own terminal. It says whether the learner got better or worse,
    and you report it (BR29).

## Phase 2 · January

13. Piece-level taste. The run ships a vector with each piece, about 0.8 KB, and the phone learns
    similarity on top of the topics. It is held until after 20 Dec because it changes the edition,
    the page and the learner at once (BR26, BR34).
14. `/paper:setup` asks the reader's country and builds their outlets from a vetted list. Setup's
    three answers weight the topics from day one (BR24, BR28).
15. Ready stage 2 is checked: a stranger gets from the install line to a first issue unaided, in
    about ten minutes.

## Phase 3 · February

16. The listing in the Claude plugin directory and a landing page, written in the dry wire-editor
    voice (BR16).
17. A handful of product reels showing a morning with the paper, paced one claim per beat (BR5,
    BR13).

## Still open

- These are Claude's proposals and not yet decided: Hungary and the EU first for primary sources,
  the order inside each phase, and which
  Hungarian roundup serves BR31.
- Unchecked: whether that roundup can be read by code; the vectors' real cost on a phone; Step 4's
  first real cloud run.

## Not on this roadmap

These were decided against: a daily public news channel, sharing posters, an image model, a
second daily issue, renaming the tool, letting the reader's taste steer the news, a fork of the
engine, and importing reading history.
