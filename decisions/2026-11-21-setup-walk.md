# Setup walk: the checklist (gap 1, D109 to D113)

In a new macOS user, signed into the Claude app, not into `gh`. Your GitHub account. It stops
before the routine.

Say first: "Name the repositories paper-data-walk and paper-reader-walk, the environment
morning-paper-walk, and stop before the routine."

At each step, note what you had to do that Claude didn't say, what stopped you, and the minutes.

1. Code tab: `/plugin install paper --marketplace VeghV03/morning-paper`, then `/paper:setup`.
   Does the app take that line? Nothing has tried it (N93).
2. Tools: how long, any password asked? Save the code from `~/paper/.tools/bin/paper cloud code`
   as a separate test entry, never over your real one.
3. The three questions: did the choices fit you?
4. `paper-data-walk`, made on github.com/new. Did Claude wait for you?
5. Environment `morning-paper-walk`: do "network access Full" and "one variable" match the
   screen? Its key comes from `paper cloud key | pbcopy` in that user's Terminal.
6. Claude's GitHub app: add `paper-data-walk` only.
7. Routine: skipped.
8. `paper-reader-walk` on Pages, then a token for `paper-data-walk` only. Open the page in that
   user's browser, not on your phone: it shares veghv03.github.io with your real page, and the
   phone keeps one store per address, so setting it up there replaces your real paper's
   settings. Expected end: "No issue yet."

Then remove: the environment, both repositories, the token, the app's reach to
`paper-data-walk`, and the macOS user.
