#!/bin/bash
# The paper's own tools, all in ~/paper/.tools: uv, Node, Python, the paper package and the news
# engine. Nothing system-wide, no package manager, no password. Run by /paper:setup, and on every
# session start with --update, which does nothing unless the plugin changed since the last install.
# macOS, Linux (glibc), and Windows under Git Bash.
#
# uv and Node are pinned builds whose checksums are written below; a download that does not match
# is refused.
set -euo pipefail

UV_VERSION=0.13.7
NODE_VERSION=v22.23.4
case "$(uname -s)" in
  Darwin) OS=mac ;;
  Linux) OS=linux ;;
  MINGW*|MSYS*|CYGWIN*) OS=windows ;;
  *) echo "paper: $(uname -s) is not supported" >&2; exit 1 ;;
esac
ARCH="$(uname -m)"
[ "$OS" = windows ] && ARCH=x86_64  # no Windows ARM build of the encryption library; x64 runs emulated
case "$OS-$ARCH" in
  mac-arm64)
    UV_FILE=uv-aarch64-apple-darwin.tar.gz; UV_SHA=81b811b57e4624df7ed3aac148e0359100d9962f3d9dce00aec533dc2e086731
    NODE_NAME=node-$NODE_VERSION-darwin-arm64; NODE_SHA=c9e1dbc748b33ed2d14f42445191ecaf14c56259c7a9a26d0042c49ec2b66428 ;;
  mac-x86_64)
    UV_FILE=uv-x86_64-apple-darwin.tar.gz; UV_SHA=20c47e4c1f630b8abaff8c291fa9b9aa300fef92c4fbff95adf198b55287cda7
    NODE_NAME=node-$NODE_VERSION-darwin-x64; NODE_SHA=efcc2b0db6f94bf53eddb038fe2b370277a042bd29e4f19b8f8e23598795b819 ;;
  linux-aarch64|linux-arm64)
    UV_FILE=uv-aarch64-unknown-linux-gnu.tar.gz; UV_SHA=71279f8d3c67241e807b9d8db872d1bf541579fb9f08b7d1eb1682196d1e57dc
    NODE_NAME=node-$NODE_VERSION-linux-arm64; NODE_SHA=f7a1e486dbc8b286847815b477d4fb5e9fb963ed4489c3e1588853d685f589f9 ;;
  linux-x86_64)
    UV_FILE=uv-x86_64-unknown-linux-gnu.tar.gz; UV_SHA=c5221ff41b7892bfc223543883600125f6a47fe845093e0f5bdff4f359196d83
    NODE_NAME=node-$NODE_VERSION-linux-x64; NODE_SHA=b8492284c76a54baf58d61668dd0e41ee0fc98adabf9503d30f05d08f55b4406 ;;
  windows-x86_64)
    UV_FILE=uv-x86_64-pc-windows-msvc.zip; UV_SHA=0cdc5b38fe5a8168ed6a25814f5ba43c21d313dd3187314fccb37b7cec46e021
    NODE_NAME=node-$NODE_VERSION-win-x64; NODE_SHA=cbc74b5e0982c9dbb41525fd8fb5dcd32fbee237863f7829072f4639a1ce5f20 ;;
  *) echo "paper: this computer's processor ($ARCH) is not supported" >&2; exit 1 ;;
esac

for tool in curl tar; do
  command -v $tool >/dev/null || { echo "paper: needs $tool (on Ubuntu or Debian: sudo apt install $tool)" >&2; exit 1; }
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"        # the plugin, wherever Claude put this version
HOME_DIR="${PAPER_HOME:-$HOME/paper}"
TOOLS="$HOME_DIR/.tools"
STAMP="$TOOLS/stamp"
EXE=""; [ "$OS" = windows ] && EXE=.exe

if [ "${1:-}" = "--update" ]; then
  [ -d "$TOOLS" ] || exit 0                       # not set up: nothing to update
  [ "$(cat "$STAMP" 2>/dev/null)" = "$ROOT" ] && exit 0
fi

mkdir -p "$TOOLS/bin" "$TOOLS/downloads"

sha() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }

fetch() {  # url, file, sha256
  local out="$TOOLS/downloads/$2"
  if [ ! -f "$out" ] || [ "$(sha "$out")" != "$3" ]; then
    curl -fsSL --retry 2 -o "$out.part" "$1"
    if [ "$(sha "$out.part")" != "$3" ]; then
      rm -f "$out.part"; echo "paper: $2 did not match its checksum; nothing was installed" >&2; exit 1
    fi
    mv "$out.part" "$out"
  fi
  echo "$out"
}

unpack() {  # archive, into
  mkdir -p "$2"
  case "$1" in
    *.zip) powershell.exe -NoProfile -Command "Expand-Archive -Force -LiteralPath '$(cygpath -w "$1")' -DestinationPath '$(cygpath -w "$2")'" ;;
    *) tar -xzf "$1" -C "$2" ;;
  esac
}

if [ "$("$TOOLS/bin/uv$EXE" --version 2>/dev/null | cut -d' ' -f2)" != "$UV_VERSION" ]; then
  f=$(fetch "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/$UV_FILE" "$UV_FILE" "$UV_SHA")
  rm -rf "$TOOLS/downloads/uv" && unpack "$f" "$TOOLS/downloads/uv"
  find "$TOOLS/downloads/uv" -name "uv$EXE" -type f -exec cp {} "$TOOLS/bin/uv$EXE" \;
  chmod +x "$TOOLS/bin/uv$EXE"
fi

if [ "$("$TOOLS/node/bin/node$EXE" --version 2>/dev/null)" != "$NODE_VERSION" ]; then
  [ "$OS" = windows ] && NODE_FILE=$NODE_NAME.zip || NODE_FILE=$NODE_NAME.tar.gz
  f=$(fetch "https://nodejs.org/dist/$NODE_VERSION/$NODE_FILE" "$NODE_FILE" "$NODE_SHA")
  rm -rf "$TOOLS/downloads/node" && unpack "$f" "$TOOLS/downloads/node"
  rm -rf "$TOOLS/node" && mkdir -p "$TOOLS/node/bin"
  # the engine needs node alone, not npm or headers
  src="$TOOLS/downloads/node/$NODE_NAME"
  if [ "$OS" = windows ]; then cp "$src/node.exe" "$TOOLS/node/bin/"; else cp "$src/bin/node" "$TOOLS/node/bin/"; fi
  cp "$src/LICENSE" "$TOOLS/node/"
fi
rm -rf "$TOOLS/downloads"

# a copy at a path that outlives the plugin's version folder; the engine keeps its record in
# src/engine/out, which moves over to the new copy
rm -rf "$TOOLS/src.new" && mkdir -p "$TOOLS/src.new"
(cd "$ROOT" && tar -cf - --exclude ./.git --exclude ./.venv --exclude ./tests --exclude ./docs \
   --exclude ./engine/out .) | tar -xf - -C "$TOOLS/src.new"
[ -d "$TOOLS/src/engine/out" ] && mv "$TOOLS/src/engine/out" "$TOOLS/src.new/engine/out"
rm -rf "$TOOLS/src" && mv "$TOOLS/src.new" "$TOOLS/src"

export UV_CACHE_DIR="$TOOLS/cache" UV_PYTHON_INSTALL_DIR="$TOOLS/python" UV_PROJECT_ENVIRONMENT="$TOOLS/venv"
"$TOOLS/bin/uv$EXE" sync --quiet --frozen --no-dev --managed-python --python 3.13 --project "$TOOLS/src"
"$TOOLS/bin/uv$EXE" cache clean --quiet

if [ "$OS" = windows ]; then PY="$TOOLS/venv/Scripts/python.exe"; else PY="$TOOLS/venv/bin/python"; fi
cat > "$TOOLS/bin/paper" <<EOF
#!/bin/bash
export PATH="$TOOLS/node/bin:\$PATH" PYTHONUTF8=1
exec "$PY" -m paper.cli "\$@"
EOF
chmod +x "$TOOLS/bin/paper"
echo "$ROOT" > "$STAMP"
echo "paper: tools ready in $TOOLS"
