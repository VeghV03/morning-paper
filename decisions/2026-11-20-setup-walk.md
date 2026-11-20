# Setup walk: the checklist (gap 1, D109 to D118)

In a new macOS user, signed into the Claude app, and into `gh` as a second GitHub account (D117,
D118). It stops before the routine.

Say first: "Name the environment morning-paper-walk, and stop before the routine." Setup's own
repository names are used as written: the second account has none of them.

At each step, note what you had to do that Claude didn't say, what stopped you, and the minutes.

1. Code tab: `/plugin install paper --marketplace VeghV03/morning-paper`, then `/paper:setup`.
   Does the app take that line? Nothing has tried it (N93).
2. Tools: how long, any password asked? Save the code from `~/paper/.tools/bin/paper cloud code`
   as a separate test entry, never over your real one.
3. The three questions: did the choices fit you?
4. `paper-data`, made by Claude with `gh` on the second account. Did it ask before making it?
5. Environment `morning-paper-walk`: do "network access Full" and "one variable" match the
   screen? Its key comes from `paper cloud key | pbcopy` in that user's Terminal.
6. Claude's GitHub app: install it on the second account, for `paper-data` only.
7. Routine: skipped.
8. `paper-reader` on Pages (the command fixed in c446300 runs here for the first time), then a
   token for `paper-data` only. Open it on your phone: on the second account it has an address of
   its own, so it can't touch your real page. Expected end: "No issue yet."
9. Run `/paper:setup` again: it should find the paper, open it, and change nothing.

Then remove: the environment, the Claude app's install on the second account, the token, the
second account's two repositories (or the account), and the macOS user.
