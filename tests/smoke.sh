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
cat > "$temp/fake-bin/launchctl" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "${KITTY_PET_LAUNCHCTL_LOG:?}"
exit 0
EOF
chmod +x "$temp/fake-bin/kitty" "$temp/fake-bin/launchctl"

export HOME="$temp/home"
export XDG_CONFIG_HOME="$temp/home/.config"
export XDG_CACHE_HOME="$temp/home/.cache"
export XDG_DATA_HOME="$temp/home/.local/share"
export XDG_RUNTIME_DIR="$temp/runtime"
export KITTY_PET_BIN_DIR="$temp/home/.local/bin"
export KITTY_PET_PLATFORM=Linux
export KITTY_PET_SKIP_SERVICE=1
export KITTY_PET_SKIP_RELOAD=1
export PATH="$temp/fake-bin:$PATH"

"$ROOT/install.sh"
"$ROOT/install.sh"

"$KITTY_PET_BIN_DIR/kitty-pet" --version
"$KITTY_PET_BIN_DIR/kitty-pet" list | grep -F "byte-cat"
"$KITTY_PET_BIN_DIR/kitty-pet" timing byte-cat running --fps 4
"$KITTY_PET_BIN_DIR/kitty-pet" timing byte-cat | grep -F "running"
python3 - <<'PY'
import json
import os
from pathlib import Path

config = json.loads((Path(os.environ["XDG_CONFIG_HOME"]) / "kitty-pet/config.json").read_text())
assert config["timings"]["pets"]["byte-cat"]["states"]["running"]["fps"] == 4
PY
"$KITTY_PET_BIN_DIR/kitty-pet" timing byte-cat running --reset
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

# Exercise the macOS installer and launchd files on every CI platform. A real
# macOS runner also exercises the native kqueue branch in the unit suite.
export KITTY_PET_PLATFORM=Darwin
export HOME="$temp/mac-home"
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_CACHE_HOME="$HOME/.cache"
export XDG_DATA_HOME="$HOME/.local/share"
unset XDG_RUNTIME_DIR
export KITTY_PET_BIN_DIR="$HOME/.local/bin"
export KITTY_PET_SKIP_SERVICE=0
export KITTY_PET_LAUNCHCTL_LOG="$temp/launchctl.log"
mkdir -p "$HOME"

"$ROOT/install.sh"
"$ROOT/install.sh"

plist="$HOME/Library/LaunchAgents/io.github.soontosh.kitty-terminal-pets.plist"
KITTY_PET_TEST_PLIST="$plist" KITTY_PET_TEST_HOME="$HOME" python3 - <<'PY'
import os
import plistlib
import stat
from pathlib import Path

path = Path(os.environ["KITTY_PET_TEST_PLIST"])
with path.open("rb") as handle:
    value = plistlib.load(handle)
assert value["Label"] == "io.github.soontosh.kitty-terminal-pets"
assert value["ProgramArguments"][-1] == "controller"
assert value["RunAtLoad"] is True
assert value["KeepAlive"] is True
assert value["ProcessType"] == "Background"
assert stat.S_IMODE(path.stat().st_mode) == 0o600
assert Path(os.environ["KITTY_PET_TEST_HOME"], "Library/Logs/KittyTerminalPets").is_dir()
PY
grep -F "bootstrap gui/$(id -u) $plist" "$KITTY_PET_LAUNCHCTL_LOG" >/dev/null
grep -F "listen_on unix:/tmp/kitty-pet-$(id -u)/kitty-pet-{kitty_pid}.sock" "$XDG_CONFIG_HOME/kitty/kitty.conf" >/dev/null
grep -F 'KITTY_PET_KITTY_BIN=' "$KITTY_PET_BIN_DIR/kitty-pet" >/dev/null

"$ROOT/uninstall.sh" --purge
grep -F "bootout gui/$(id -u) $plist" "$KITTY_PET_LAUNCHCTL_LOG" >/dev/null
[[ ! -e "$plist" ]]
[[ ! -e "$KITTY_PET_BIN_DIR/kitty-pet" ]]

printf 'Smoke test passed.\n'
