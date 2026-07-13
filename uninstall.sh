#!/usr/bin/env bash
set -euo pipefail

HOME=${HOME:?HOME is not set}
CONFIG_HOME=${XDG_CONFIG_HOME:-$HOME/.config}
DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}
BIN_DIR=${KITTY_PET_BIN_DIR:-$HOME/.local/bin}
APP_DIR="$DATA_HOME/kitty-pet"
KITTY_CONFIG="$CONFIG_HOME/kitty/kitty.conf"
SERVICE_FILE="$CONFIG_HOME/systemd/user/kitty-pet.service"
PURGE=0
SKIP_SERVICE=${KITTY_PET_SKIP_SERVICE:-0}
SKIP_RELOAD=${KITTY_PET_SKIP_RELOAD:-0}
[[ ${1:-} == --purge ]] && PURGE=1

if [[ -x "$BIN_DIR/kitty-pet" ]]; then
    "$BIN_DIR/kitty-pet" close >/dev/null 2>&1 || true
fi
if [[ $SKIP_SERVICE != 1 ]] && command -v systemctl >/dev/null 2>&1; then
    systemctl --user disable --now kitty-pet.service >/dev/null 2>&1 || true
fi
rm -f "$SERVICE_FILE"
if [[ $SKIP_SERVICE != 1 ]] && command -v systemctl >/dev/null 2>&1; then
    systemctl --user daemon-reload >/dev/null 2>&1 || true
fi

if [[ -f "$KITTY_CONFIG" ]]; then
    KITTY_PET_KITTY_CONFIG="$KITTY_CONFIG" python3 - <<'PY'
import os, re
from pathlib import Path
path = Path(os.environ["KITTY_PET_KITTY_CONFIG"])
text = path.read_text()
for name in ("kitty-pet", "kitty-pet-safe", "kitty-terminal-pets"):
    text = re.sub(rf"\n?# >>> {re.escape(name)} >>>.*?# <<< {re.escape(name)} <<<\n?", "\n", text, flags=re.S)
path.write_text(text.rstrip() + "\n")
PY
fi

rm -f "$BIN_DIR/kitty-pet"
rm -rf "$APP_DIR"
if (( PURGE )); then
    rm -rf "$CONFIG_HOME/kitty-pet" "$DATA_HOME/terminal-pets/pets/byte-cat"
fi

if [[ $SKIP_RELOAD != 1 ]]; then
    for pid in $(pgrep -x kitty 2>/dev/null || true); do
        kill -USR1 "$pid" 2>/dev/null || true
    done
fi

printf 'kitty-pet: uninstalled%s. Restart Kitty to remove the old socket.\n' "$([[ $PURGE == 1 ]] && printf ' and purged settings' || true)"
