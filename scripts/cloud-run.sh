#!/bin/bash
# The morning run in the cloud (D45). `start` opens the reader's data repository into ~/paper and
# puts the `paper` command where the today skill calls it; `finish` seals what changed back and
# pushes it. Between the two, Claude follows skills/today/SKILL.md as on a computer.
#
# The run needs PAPER_RUN_KEY in the cloud environment's variables (`paper cloud key` prints it
# on the computer that ran setup) and the data repository cloned beside this one, or named in
# PAPER_DATA. `start` also downloads the text encoder (D103) when it is not there yet; to keep it
# in the environment's cache, the setup script can run `bash morning-paper/scripts/cloud-run.sh model`.
# Without it the feed and publish fall back and say so.
set -euo pipefail

PLUGIN="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${PAPER_DATA:-$PLUGIN/../paper-data}"
export PAPER_HOME="${PAPER_HOME:-$HOME/paper}"
BIN="$PAPER_HOME/.tools/bin"

tools() {
  command -v uv >/dev/null || python3 -m pip install --quiet --user uv
  export PATH="$HOME/.local/bin:$PATH"
  uv sync --quiet --frozen --no-dev --project "$PLUGIN"
}
model() {
  "$PLUGIN/.venv/bin/python" -m paper.cli model || echo "paper: no text encoder; stories are grouped by the engine alone" >&2
}

if [ "${1:-}" = model ]; then tools; model; exit 0; fi

[ -n "${PAPER_RUN_KEY:-}" ] || { echo "paper: set PAPER_RUN_KEY in the cloud environment's variables" >&2; exit 1; }
[ -d "$DATA/.git" ] || { echo "paper: the data repository is not at $DATA; add it to the task, or set PAPER_DATA" >&2; exit 1; }

case "${1:-}" in
  start)
    tools
    mkdir -p "$BIN"
    cat > "$BIN/paper" <<EOF
#!/bin/bash
export PAPER_HOME="$PAPER_HOME" PYTHONUTF8=1  # the run key stays in the environment, never in a file
exec "$PLUGIN/.venv/bin/python" -m paper.cli "\$@"
EOF
    chmod +x "$BIN/paper"
    "$BIN/paper" cloud unpack --repo "$DATA"
    model  # after the reader's files are open: a failed download costs the merging, never the run
    ;;
  finish)
    "$BIN/paper" cloud pack --repo "$DATA"
    cd "$DATA"
    git add -A
    if git diff --cached --quiet; then echo "paper: nothing changed"; exit 0; fi
    git -c user.name="Morning paper" -c user.email="paper@localhost" commit --quiet -m "Issue $(date -u +%F)"
    # a device may have written its record and brief while the run worked: those files are not the
    # run's, so they come in without a conflict
    git pull --quiet --rebase origin main
    git push --quiet origin HEAD:main
    echo "paper: sealed and pushed"
    ;;
  *) echo "usage: cloud-run.sh start|finish|model" >&2; exit 1 ;;
esac
