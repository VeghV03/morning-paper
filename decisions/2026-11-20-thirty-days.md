# 2026-11-20 · Counting the 30 days

Stage 1 of "ready" is the reader's own 30 days (MP-B1, copied below). Answered by the reader in two
multiple-choice rounds. Numbered T.

**Found first:** each run already pushes a commit named "Issue <date>" to the data repository, with
its time (20 Nov: 05:12), so a delivery is on record without new logging. The devices' week files
hold what was opened and read, under the record key. The computer that ran setup keeps the recovery
code, so I think it can open them; not tried on the real record.

## MP-B1 · What "world class" is measured by (from the brain's log, 2026-11-20)
**Chosen:** both, in order: the reader's own 30 days (mornings delivered, opened, pieces finished),
then a stranger sets up unaided in about ten minutes.

## T1 · The delivery record
**Chosen:** what exists: the run's commit time in the data repository's history.
**Not chosen:** a line a morning in a sealed file; the phone noting when an issue arrived (a morning
not opened would look like a morning nothing came).
**Accepted cost:** a failed run is only a missing day, with no reason; a hand-fired issue is told
apart only by its hour; squashing the repository's history loses the times.

## T2 · Who sees the counts
**Chosen:** the reader alone, in their own terminal. A Claude session is told pass or fail.
**Not chosen:** a Claude session on the reader's computer running the tally. Never offered: counts
where the run could read them (D47).
**Accepted cost:** a session cannot check stage 1 itself.

## T3 · Where the tally is read
**Chosen:** the terminal: a row a morning and three totals, nothing written to disk.
**Not chosen:** a page on the phone (reopens MP-B5); a file on the computer (D16).

## T4 · Whose tool
**Chosen:** the reader's alone for now: a command left out of the README, setup and skills.
**Not chosen:** a documented command for every reader.

## T5 · Delivered
**Chosen:** the day's "Issue" commit lands by 06:00, the computer's local time.
**Not chosen:** by 07:00; any time that day.
**Accepted cost:** an issue at 06:10 is a miss.

## T6 · Opened and finished
**Chosen:** opened: the day's front page shown on its own calendar day. Finished: at least one of
its pieces finished that day, by the paper's own rule. The total of pieces finished is printed too.
**Not chosen:** any time in the 30 days; finished as a share of pieces.
**Accepted cost:** catching up on yesterday's paper earns yesterday nothing.

## T7 · The window
**Chosen:** 21 November to 20 December 2026, fixed; a miss counts against the share.
**Not chosen:** from 20 November (its record holds test taps, I think); from the redesign; any 30
days in a row that pass.
**Accepted cost:** the redesign and step 4 land inside the window.

## T8 · The pass mark
**Chosen:** of 30 mornings: 27 delivered, 21 opened, 15 with a piece finished. The numbers are
Claude's guesses, measured against nothing.
**Not chosen:** 30, 26, 20; a mark for delivery only; a mark set after 10 days.
**Accepted cost:** a morning read on the X4 shows as unopened; changing the mark later weakens the test.

## As built
`paper days --repo <a clone of the data repository> --from 2026-11-21` (`src/paper/days.py`) prints
the table. It opens the month files with the run key and the devices' week files with the record
key, both made in memory from the computer's recovery code, and writes nothing.

**Assumed, not asked:**
- Outside a terminal (a session's shell, a pipe, a file) the command prints nothing and says why:
  T2 as a guard against a slip, not a lock.
- It fetches the clone first; when that fails it says so and counts what is there.
- "The front page shown" is read as any first showing, look, open or read of one of the day's
  pieces, made that day. The page logs a piece as shown only the first time, so on the issue's own
  day this is the same thing.
- Days are cut in the time zone of the computer the tally runs on. Run from another time zone, the
  06:00 line and the day's edges move.
- A day belongs to the commit's local date, which for a reader in Europe is the date in its name.
- The first day is given on the command line, not kept in the tool, which other readers also install.
- Today's row shows as not delivered until the issue lands.

**Checked (2026-11-20):** on a made-up repository (`tests/test_days.py`): a morning delivered,
opened and finished; a late issue; a second run the same day; a rebuilt edition's commit; reading a
day late; a quick scroll; the 30-day edge; the pass mark at 27 and 26; another code; no output
outside a terminal. The table read in a terminal on the same made-up repository.
**Not yet checked:** the real data repository; whether this computer's code opens the phone's
record; Windows and Linux.
