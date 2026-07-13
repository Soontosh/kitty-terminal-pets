#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
temp=$(mktemp -d)
trap 'rm -rf "$temp"' EXIT

python3 -m compileall -q "$ROOT/src" "$ROOT/demo/generate_assets.py"
python3 -m json.tool "$ROOT/assets/byte-cat/pet.json" >/dev/null
python3 -m unittest discover -s "$ROOT/tests" -v

mkdir -p "$temp/fake-bin" "$temp/home"
cat > "$temp/fake-bin/kitty" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$temp/fake-bin/kitty"

export HOME="$temp/home"
export XDG_CONFIG_HOME="$temp/home/.config"
export XDG_CACHE_HOME="$temp/home/.cache"
export XDG_DATA_HOME="$temp/home/.local/share"
export XDG_RUNTIME_DIR="$temp/runtime"
export KITTY_PET_BIN_DIR="$temp/home/.local/bin"
export KITTY_PET_SKIP_SERVICE=1
export KITTY_PET_SKIP_RELOAD=1
export PATH="$temp/fake-bin:$PATH"

"$ROOT/install.sh"
"$ROOT/install.sh"

"$KITTY_PET_BIN_DIR/kitty-pet" --version
"$KITTY_PET_BIN_DIR/kitty-pet" list | grep -F "byte-cat"
"$KITTY_PET_BIN_DIR/kitty-pet" self-test

config="$XDG_CONFIG_HOME/kitty/kitty.conf"
[[ $(grep -c '^# >>> kitty-terminal-pets >>>$' "$config") == 1 ]]
grep -F 'allow_remote_control socket-only' "$config" >/dev/null

"$ROOT/uninstall.sh" --purge
if grep -F 'kitty-terminal-pets' "$config" >/dev/null; then
    printf 'Managed Kitty block survived uninstall.\n' >&2
    exit 1
fi
[[ ! -e "$KITTY_PET_BIN_DIR/kitty-pet" ]]

printf 'Smoke test passed.\n'
