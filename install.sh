#!/usr/bin/env bash
set -euo pipefail

REPOSITORY="https://github.com/Soontosh/kitty-terminal-pets.git"
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)

# Support the convenient curl | bash route without making the real installer
# depend on files that were not downloaded.
if [[ ! -f "$ROOT/src/kitty_pet.py" ]]; then
    command -v git >/dev/null 2>&1 || { echo "kitty-pet: git is required" >&2; exit 1; }
    temp=$(mktemp -d)
    trap 'rm -rf "$temp"' EXIT
    git clone --quiet --depth 1 "$REPOSITORY" "$temp/repo"
    exec "$temp/repo/install.sh" "$@"
fi

HOME=${HOME:?HOME is not set}
PLATFORM=${KITTY_PET_PLATFORM:-$(uname -s)}
case "$PLATFORM" in
    Linux) SERVICE_MANAGER=systemd ;;
    Darwin) SERVICE_MANAGER=launchd ;;
    *) printf 'kitty-pet: only Linux and macOS are supported (found %s)\n' "$PLATFORM" >&2; exit 1 ;;
esac
CONFIG_HOME=${XDG_CONFIG_HOME:-$HOME/.config}
DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}
BIN_DIR=${KITTY_PET_BIN_DIR:-$HOME/.local/bin}
APP_DIR="$DATA_HOME/kitty-pet"
PET_ROOT="$DATA_HOME/terminal-pets/pets"
CONFIG_DIR="$CONFIG_HOME/kitty-pet"
KITTY_DIR="$CONFIG_HOME/kitty"
KITTY_CONFIG="$KITTY_DIR/kitty.conf"
SYSTEMD_DIR="$CONFIG_HOME/systemd/user"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"
LAUNCHD_LABEL="io.github.soontosh.kitty-terminal-pets"
LOG_DIR="$HOME/Library/Logs/KittyTerminalPets"
if [[ $SERVICE_MANAGER == systemd ]]; then
    SERVICE_FILE="$SYSTEMD_DIR/kitty-pet.service"
else
    SERVICE_FILE="$LAUNCHD_DIR/$LAUNCHD_LABEL.plist"
fi
SOCKET_DIR=${KITTY_PET_SOCKET_DIR:-${XDG_RUNTIME_DIR:-/tmp/kitty-pet-$(id -u)}}
SKIP_SERVICE=${KITTY_PET_SKIP_SERVICE:-0}
SKIP_RELOAD=${KITTY_PET_SKIP_RELOAD:-0}

say() { printf '\033[1;36mkitty-pet:\033[0m %s\n' "$*"; }
die() { printf 'kitty-pet: %s\n' "$*" >&2; exit 1; }

command -v python3 >/dev/null 2>&1 || die "Python 3.10+ is required"
python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' || die "Python 3.10+ is required"

KITTY_BIN=${KITTY_PET_KITTY_BIN:-}
if [[ -z $KITTY_BIN ]] && command -v kitty >/dev/null 2>&1; then
    KITTY_BIN=$(command -v kitty)
fi
if [[ -z $KITTY_BIN && $SERVICE_MANAGER == launchd ]]; then
    for candidate in \
        /Applications/kitty.app/Contents/MacOS/kitty \
        "$HOME/Applications/kitty.app/Contents/MacOS/kitty"; do
        if [[ -x $candidate ]]; then
            KITTY_BIN=$candidate
            break
        fi
    done
fi
[[ -n $KITTY_BIN && -x $KITTY_BIN ]] || die "Kitty is required: https://sw.kovidgoyal.net/kitty/binary/"

mkdir -p "$APP_DIR" "$PET_ROOT/byte-cat" "$CONFIG_DIR" "$KITTY_DIR" "$BIN_DIR" "$SOCKET_DIR"
chmod 700 "$SOCKET_DIR"
if [[ $SERVICE_MANAGER == systemd ]]; then
    mkdir -p "$SYSTEMD_DIR"
else
    mkdir -p "$LAUNCHD_DIR" "$LOG_DIR"
fi

if [[ -x "$BIN_DIR/kitty-pet" ]]; then
    "$BIN_DIR/kitty-pet" close >/dev/null 2>&1 || true
fi
if [[ $SKIP_SERVICE != 1 && $SERVICE_MANAGER == systemd ]] && command -v systemctl >/dev/null 2>&1; then
    systemctl --user stop kitty-pet.service >/dev/null 2>&1 || true
elif [[ $SKIP_SERVICE != 1 && $SERVICE_MANAGER == launchd ]] && command -v launchctl >/dev/null 2>&1; then
    launchctl bootout "gui/$(id -u)" "$SERVICE_FILE" >/dev/null 2>&1 || true
fi

say "Installing the app"
install -m 0755 "$ROOT/src/kitty_pet.py" "$APP_DIR/kitty_pet.py"
install -m 0644 "$ROOT/README.md" "$APP_DIR/README.md"
install -m 0644 "$ROOT/assets/byte-cat/pet.json" "$PET_ROOT/byte-cat/pet.json"
install -m 0644 "$ROOT/assets/byte-cat/spritesheet.webp" "$PET_ROOT/byte-cat/spritesheet.webp"

if [[ ! -x "$APP_DIR/venv/bin/python" ]]; then
    python3 -m venv --system-site-packages "$APP_DIR/venv" || die "Could not create a Python venv (install python3-venv, then retry)"
fi
if ! "$APP_DIR/venv/bin/python" -c 'from PIL import Image' >/dev/null 2>&1; then
    say "Installing the Pillow image dependency"
    "$APP_DIR/venv/bin/python" -m pip install --quiet --disable-pip-version-check 'Pillow>=10,<13'
fi
"$APP_DIR/venv/bin/python" -m compileall -q "$APP_DIR/kitty_pet.py"

wrapper=$(mktemp)
printf '#!/usr/bin/env bash\nset -euo pipefail\nexport KITTY_PET_BIN=%q\nexport KITTY_PET_KITTY_BIN=%q\nexport KITTY_PET_SOCKET_DIR=%q\nexec %q %q "$@"\n' \
    "$BIN_DIR/kitty-pet" "$KITTY_BIN" "$SOCKET_DIR" \
    "$APP_DIR/venv/bin/python" "$APP_DIR/kitty_pet.py" > "$wrapper"
install -m 0755 "$wrapper" "$BIN_DIR/kitty-pet"
rm -f "$wrapper"

say "Preparing the shared pet catalog"
KITTY_PET_CONFIG_FILE="$CONFIG_DIR/config.json" \
KITTY_PET_CODEX_ROOT="$HOME/.codex/pets" \
KITTY_PET_SHARED_ROOT="$PET_ROOT" \
python3 - <<'PY'
import json, os, tempfile
from pathlib import Path

path = Path(os.environ["KITTY_PET_CONFIG_FILE"])
codex = Path(os.environ["KITTY_PET_CODEX_ROOT"])
shared = Path(os.environ["KITTY_PET_SHARED_ROOT"])
try:
    config = json.loads(path.read_text()) if path.is_file() else {}
except (OSError, json.JSONDecodeError):
    config = {}
roots = [str(codex), str(shared)]
config["pet_roots"] = list(dict.fromkeys([*config.get("pet_roots", []), *roots]))
available = {manifest.parent.name for root in (codex, shared) for manifest in root.glob("*/pet.json")}
if config.get("pet") not in available:
    config["pet"] = "killua" if "killua" in available else (sorted(available)[0] if available else "byte-cat")
config.setdefault("enabled", True)
config.setdefault("pane_percent", 13)
config.setdefault("pet_rows", 7)
config.setdefault("cursor_offset_rows", 1)
config.setdefault("completion_seconds", 2.5)
config.setdefault("controller_poll_seconds", 1.0)
config.setdefault("startup_delay_seconds", 0.75)
config.setdefault("timings", {})
path.parent.mkdir(parents=True, exist_ok=True)
fd, raw = tempfile.mkstemp(prefix=".config.", dir=path.parent)
with os.fdopen(fd, "w") as handle:
    json.dump(config, handle, indent=2)
    handle.write("\n")
os.chmod(raw, 0o600)
os.replace(raw, path)
PY

say "Adding the safe Kitty configuration"
if [[ -f "$KITTY_CONFIG" ]]; then
    cp -p "$KITTY_CONFIG" "$KITTY_CONFIG.kitty-pet-backup.$(date +%Y%m%d%H%M%S)"
else
    : > "$KITTY_CONFIG"
fi
KITTY_PET_KITTY_CONFIG="$KITTY_CONFIG" KITTY_PET_BIN="$BIN_DIR/kitty-pet" KITTY_PET_SOCKET_DIR="$SOCKET_DIR" python3 - <<'PY'
import os, re, shlex
from pathlib import Path

path = Path(os.environ["KITTY_PET_KITTY_CONFIG"])
binary = shlex.quote(os.environ["KITTY_PET_BIN"])
socket_dir = os.environ["KITTY_PET_SOCKET_DIR"]
if any(character in socket_dir for character in "\n\r"):
    raise SystemExit("kitty-pet: invalid socket directory")
text = path.read_text()
for name in ("kitty-pet", "kitty-pet-safe", "kitty-terminal-pets"):
    text = re.sub(rf"\n?# >>> {re.escape(name)} >>>.*?# <<< {re.escape(name)} <<<\n?", "\n", text, flags=re.S)
block = f'''# >>> kitty-terminal-pets >>>
# Local Unix sockets only: pet management never shares the keyboard TTY.
allow_remote_control socket-only
listen_on unix:{socket_dir}/kitty-pet-{{kitty_pid}}.sock

# Borderless internal rail; native OS window decorations are untouched.
window_border_width 0
draw_minimal_borders yes
draw_window_borders_for_single_window no

map ctrl+shift+f8 launch --type=overlay --title="Select terminal pet" {binary} select
map ctrl+shift+f7 launch --type=background {binary} toggle
# <<< kitty-terminal-pets <<<
'''
path.write_text(text.rstrip() + "\n\n" + block)
PY

if [[ $SERVICE_MANAGER == systemd ]]; then
    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Kitty Terminal Pets socket controller
Documentation=https://github.com/Soontosh/kitty-terminal-pets

[Service]
Type=simple
ExecStart=$BIN_DIR/kitty-pet controller
Restart=on-failure
RestartSec=2
Nice=10
CPUWeight=10
IOWeight=10
IOSchedulingClass=idle

[Install]
WantedBy=default.target
EOF
else
    KITTY_PET_PLIST="$SERVICE_FILE" \
    KITTY_PET_LABEL="$LAUNCHD_LABEL" \
    KITTY_PET_BIN="$BIN_DIR/kitty-pet" \
    KITTY_PET_LOG_DIR="$LOG_DIR" \
    python3 - <<'PY'
import os
import plistlib
from pathlib import Path

path = Path(os.environ["KITTY_PET_PLIST"])
log_dir = Path(os.environ["KITTY_PET_LOG_DIR"])
value = {
    "Label": os.environ["KITTY_PET_LABEL"],
    "ProgramArguments": [os.environ["KITTY_PET_BIN"], "controller"],
    "RunAtLoad": True,
    "KeepAlive": True,
    "ThrottleInterval": 2,
    "ProcessType": "Background",
    "LowPriorityIO": True,
    "Nice": 10,
    "StandardOutPath": str(log_dir / "controller.log"),
    "StandardErrorPath": str(log_dir / "controller-error.log"),
}
with path.open("wb") as handle:
    plistlib.dump(value, handle, sort_keys=False)
PY
    chmod 600 "$SERVICE_FILE"
fi

"$BIN_DIR/kitty-pet" self-test

if [[ $SKIP_SERVICE != 1 ]]; then
    if [[ $SERVICE_MANAGER == systemd ]]; then
        command -v systemctl >/dev/null 2>&1 || die "systemd user services are required on Linux"
        systemctl --user daemon-reload
        systemctl --user enable --now kitty-pet.service
    else
        command -v launchctl >/dev/null 2>&1 || die "launchd is required on macOS"
        domain="gui/$(id -u)"
        launchctl enable "$domain/$LAUNCHD_LABEL" >/dev/null 2>&1 || true
        launchctl bootstrap "$domain" "$SERVICE_FILE" || die "could not start the launch agent; run the installer from your logged-in macOS desktop"
    fi
fi

if [[ $SKIP_RELOAD != 1 ]]; then
    for pid in $(pgrep -f '(^|/)kitty( |$)|kitty.app/Contents/MacOS/kitty' 2>/dev/null || true); do
        kill -USR1 "$pid" 2>/dev/null || true
    done
fi

say "Installed! Fully quit and reopen Kitty once so its local socket is created."
say "Then run: kitty-pet select"
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) say "$BIN_DIR is not on PATH; use $BIN_DIR/kitty-pet or add that directory to your shell PATH." ;;
esac
