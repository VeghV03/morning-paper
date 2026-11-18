#!/bin/bash
# The paper's own tools, all in ~/paper/.tools: uv, Node, Python, the paper package and the news
# engine. Nothing system-wide, no Homebrew, no password. Run by /paper:setup, and on every session
# start with --update, which does nothing unless the plugin changed since the last install.
#
# uv and Node are pinned builds whose checksums are written below; a download that does not match
# is refused.
set -euo pipefail

UV_VERSION=0.13.7
NODE_VERSION=v22.23.4
case "$(uname -m)" in
  arm64) UV_ARCH=aarch64; NODE_ARCH=arm64
         UV_SHA=81b811b57e4624df7ed3aac148e0359100d9962f3d9dce00aec533dc2e086731
         NODE_SHA=c9e1dbc748b33ed2d14f42445191ecaf14c56259c7a9a26d0042c49ec2b66428 ;;
  x86_64) UV_ARCH=x86_64; NODE_ARCH=x64
         UV_SHA=20c47e4c1f630b8abaff8c291fa9b9aa300fef92c4fbff95adf198b55287cda7
         NODE_SHA=efcc2b0db6f94bf53eddb038fe2b370277a042bd29e4f19b8f8e23598795b819 ;;
  *) echo "paper: this Mac's processor ($(uname -m)) is not supported" >&2; exit 1 ;;
esac

ROOT="$(cd "$(dirname "$0")/.." && pwd)"        # the plugin, wherever Claude put this version
HOME_DIR="${PAPER_HOME:-$HOME/paper}"
TOOLS="$HOME_DIR/.tools"
STAMP="$TOOLS/stamp"

if [ "${1:-}" = "--update" ]; then
  [ -d "$TOOLS" ] || exit 0                       # not set up: nothing to update
  [ "$(cat "$STAMP" 2>/dev/null)" = "$ROOT" ] && exit 0
fi

mkdir -p "$TOOLS/bin" "$TOOLS/downloads"

fetch() {  # url, file, sha256
  local out="$TOOLS/downloads/$2"
  if [ ! -f "$out" ] || [ "$(shasum -a 256 "$out" | cut -d' ' -f1)" != "$3" ]; then
    curl -fsSL --retry 2 -o "$out.part" "$1"
    if [ "$(shasum -a 256 "$out.part" | cut -d' ' -f1)" != "$3" ]; then
      rm -f "$out.part"; echo "paper: $2 did not match its checksum; nothing was installed" >&2; exit 1
    fi
    mv "$out.part" "$out"
  fi
  echo "$out"
}

if [ "$("$TOOLS/bin/uv" --version 2>/dev/null | cut -d' ' -f2)" != "$UV_VERSION" ]; then
  f=$(fetch "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-$UV_ARCH-apple-darwin.tar.gz" \
            "uv-$UV_VERSION.tar.gz" "$UV_SHA")
  tar -xzf "$f" -C "$TOOLS/bin" --strip-components 1 "uv-$UV_ARCH-apple-darwin/uv"
fi

if [ "$("$TOOLS/node/bin/node" --version 2>/dev/null)" != "$NODE_VERSION" ]; then
  f=$(fetch "https://nodejs.org/dist/$NODE_VERSION/node-$NODE_VERSION-darwin-$NODE_ARCH.tar.gz" \
            "node-$NODE_VERSION.tar.gz" "$NODE_SHA")
  rm -rf "$TOOLS/node" && mkdir -p "$TOOLS/node/bin"
  tar -xzf "$f" -C "$TOOLS/node" --strip-components 1 "node-$NODE_VERSION-darwin-$NODE_ARCH/bin/node" \
    "node-$NODE_VERSION-darwin-$NODE_ARCH/LICENSE"  # the engine needs node alone, not npm or headers
fi
rm -rf "$TOOLS/downloads"

# a copy at a path that outlives the plugin's version folder; the engine keeps its record in it
rsync -a --delete --exclude .git --exclude .venv --exclude tests --exclude docs --exclude 'engine/out' \
  "$ROOT/" "$TOOLS/src/"

export UV_CACHE_DIR="$TOOLS/cache" UV_PYTHON_INSTALL_DIR="$TOOLS/python" UV_PROJECT_ENVIRONMENT="$TOOLS/venv"
"$TOOLS/bin/uv" sync --quiet --frozen --no-dev --managed-python --python 3.13 --project "$TOOLS/src"
"$TOOLS/bin/uv" cache clean --quiet

cat > "$TOOLS/bin/paper" <<EOF
#!/bin/bash
export PATH="$TOOLS/node/bin:\$PATH"
exec "$TOOLS/venv/bin/python" -m paper.cli "\$@"
EOF
chmod +x "$TOOLS/bin/paper"
echo "$ROOT" > "$STAMP"

# the reader server runs the copy; after an update it restarts on the new code
launchctl kickstart -k "gui/$(id -u)/local.morning-paper.serve" >/dev/null 2>&1 || true
echo "paper: tools ready in $TOOLS"
