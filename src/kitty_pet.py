#!/usr/bin/env python3
"""Kitty-wide animated pets backed by the Codex/Petdex pet registry."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import socket as socket_lib
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image


__version__ = "1.0.0"

HOME = Path.home()
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / "kitty-pet"
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache")) / "kitty-pet"
RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", f"/tmp/kitty-pet-{os.getuid()}")) / "kitty-pet"
STATE_DIR = RUNTIME_DIR / "states"
POSITION_DIR = RUNTIME_DIR / "positions"
CODEX_PETS = Path(os.environ.get("CODEX_HOME", HOME / ".codex")) / "pets"
SOCKET_GLOB = "kitty-pet-*.sock"

DEFAULT_CONFIG: dict[str, Any] = {
    "pet": "killua",
    "enabled": True,
    "pet_roots": [str(CODEX_PETS), str(HOME / ".local/share/terminal-pets/pets")],
    "pane_percent": 13,
    "pet_rows": 7,
    "cursor_offset_rows": 1,
    "completion_seconds": 2.5,
}

FRAME_DEFAULTS = {"width": 192, "height": 208, "columns": 8, "rows": 9}

# These timings and rows mirror the defaults in Codex's pet model. Terminal
# task animations intentionally loop their primary state indefinitely.
DEFAULT_TRACKS: dict[str, tuple[list[int], list[int]]] = {
    "idle": ([0, 1, 2, 3, 4, 5], [1680, 660, 660, 840, 840, 1920]),
    "running": ([56, 57, 58, 59, 60, 61], [120, 120, 120, 120, 120, 220]),
    "review": ([64, 65, 66, 67, 68, 69], [150, 150, 150, 150, 150, 280]),
    "failed": ([40, 41, 42, 43, 44, 45, 46, 47], [140, 140, 140, 140, 140, 140, 140, 240]),
    "waiting": ([48, 49, 50, 51, 52, 53], [150, 150, 150, 150, 150, 260]),
}


class PetError(RuntimeError):
    pass


@dataclass(frozen=True)
class Pet:
    pet_id: str
    display_name: str
    description: str
    directory: Path
    sheet: Path
    frame: dict[str, int]
    animations: dict[str, Any]


def ensure_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    POSITION_DIR.mkdir(parents=True, exist_ok=True)


def atomic_json(path: Path, value: Any, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)
            handle.write("\n")
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def load_config() -> dict[str, Any]:
    ensure_dirs()
    config = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.is_file():
        try:
            raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                config.update(raw)
        except (OSError, json.JSONDecodeError) as exc:
            raise PetError(f"cannot read {CONFIG_FILE}: {exc}") from exc
    return config


def save_config(config: dict[str, Any]) -> None:
    atomic_json(CONFIG_FILE, config, 0o600)


def discover_pets(config: dict[str, Any] | None = None) -> dict[str, Pet]:
    config = config or load_config()
    pets: dict[str, Pet] = {}
    for raw_root in config.get("pet_roots", DEFAULT_CONFIG["pet_roots"]):
        root = Path(os.path.expanduser(str(raw_root)))
        if not root.is_dir():
            continue
        for manifest in sorted(root.glob("*/pet.json")):
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue
                pet_id = str(data.get("id") or manifest.parent.name).strip()
                if not pet_id or pet_id in pets:
                    continue
                sheet_name = str(data.get("spritesheetPath") or "spritesheet.webp")
                sheet = (manifest.parent / sheet_name).resolve()
                if not sheet.is_file() or manifest.parent.resolve() not in sheet.parents:
                    continue
                frame = dict(FRAME_DEFAULTS)
                if isinstance(data.get("frame"), dict):
                    for key in frame:
                        if key in data["frame"]:
                            frame[key] = int(data["frame"][key])
                pets[pet_id] = Pet(
                    pet_id=pet_id,
                    display_name=str(data.get("displayName") or pet_id),
                    description=str(data.get("description") or ""),
                    directory=manifest.parent,
                    sheet=sheet,
                    frame=frame,
                    animations=data.get("animations") if isinstance(data.get("animations"), dict) else {},
                )
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
    return pets


def selected_pet(config: dict[str, Any] | None = None) -> Pet:
    config = config or load_config()
    pets = discover_pets(config)
    pet_id = str(config.get("pet", "killua"))
    if pet_id not in pets:
        choices = ", ".join(sorted(pets)) or "none found"
        raise PetError(f"selected pet {pet_id!r} is unavailable; available pets: {choices}")
    return pets[pet_id]


def animation_spec(pet: Pet, state: str) -> tuple[list[int], list[int]]:
    manifest_name = "review" if state == "success" else state
    custom = pet.animations.get(manifest_name)
    if isinstance(custom, dict) and isinstance(custom.get("frames"), list) and custom["frames"]:
        frames = [int(item) for item in custom["frames"]]
        fps = float(custom.get("fps", 8.0))
        if not 0 < fps <= 60:
            raise PetError(f"invalid {manifest_name} fps for {pet.pet_id}: {fps}")
        return frames, [max(17, round(1000 / fps))] * len(frames)
    return DEFAULT_TRACKS.get(manifest_name, DEFAULT_TRACKS["idle"])


def build_animation(pet: Pet, state: str) -> Path:
    frames, durations = animation_spec(pet, state)
    source_hash = hashlib.sha256()
    source_hash.update(pet.sheet.read_bytes())
    source_hash.update(json.dumps([pet.frame, frames, durations], sort_keys=True).encode())
    target = CACHE_DIR / pet.pet_id / f"{state}-{source_hash.hexdigest()[:16]}.webp"
    if target.is_file():
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(pet.sheet) as sheet:
        width = pet.frame["width"]
        height = pet.frame["height"]
        columns = pet.frame["columns"]
        rows = pet.frame["rows"]
        expected = (width * columns, height * rows)
        if sheet.size != expected:
            raise PetError(f"{pet.sheet} is {sheet.size[0]}x{sheet.size[1]}, expected {expected[0]}x{expected[1]}")
        limit = columns * rows
        images: list[Image.Image] = []
        for index in frames:
            if not 0 <= index < limit:
                raise PetError(f"animation {state} references frame {index}, but {pet.pet_id} has {limit} frames")
            x = (index % columns) * width
            y = (index // columns) * height
            images.append(sheet.crop((x, y, x + width, y + height)).convert("RGBA"))

    fd, raw = tempfile.mkstemp(prefix=".animation-", suffix=".webp", dir=target.parent)
    os.close(fd)
    tmp = Path(raw)
    try:
        images[0].save(
            tmp,
            format="WEBP",
            save_all=True,
            append_images=images[1:],
            duration=durations,
            loop=0,
            lossless=True,
            method=4,
        )
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
        for image in images:
            image.close()
    return target


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def effective_state(config: dict[str, Any] | None = None) -> str:
    config = config or load_config()
    now = time.time()
    recent: list[tuple[float, str]] = []
    ensure_dirs()
    for path in STATE_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            pid = int(data["pid"])
            stamp = float(data["timestamp"])
            state = str(data["state"])
            if not pid_alive(pid):
                path.unlink(missing_ok=True)
                continue
            if state == "running":
                return "running"
            recent.append((stamp, state))
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            path.unlink(missing_ok=True)
    if recent:
        stamp, state = max(recent)
        if now - stamp <= float(config.get("completion_seconds", 2.5)) and state in {"success", "failed", "waiting"}:
            return state
    return "idle"


def write_state(kind: str, pid: int, exit_code: int = 0) -> None:
    if kind == "done":
        kind = "success" if exit_code == 0 else "failed"
    if kind not in {"idle", "running", "success", "failed", "waiting"}:
        raise PetError(f"unknown state: {kind}")
    atomic_json(STATE_DIR / f"{pid}.json", {"pid": pid, "state": kind, "timestamp": time.time()}, 0o600)


def kitty_socket_command(socket: Path, *args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    """Run a Kitty command over a Unix socket, never through a terminal TTY."""
    command = ["kitty", "@", f"--to=unix:{socket}", *args]
    try:
        return subprocess.run(
            command,
            text=True,
            capture_output=capture,
            check=False,
            timeout=8,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return subprocess.CompletedProcess(command, 124, stdout, stderr)


def kitty_socket_request(socket: Path, command: str, payload: dict[str, Any]) -> str | None:
    """Use Kitty's framed JSON protocol directly for frequent read-only queries."""
    request = {
        "cmd": command,
        "version": [0, 26, 0],
        "kitty_window_id": 0,
        "payload": payload,
    }
    message = b"\x1bP@kitty-cmd" + json.dumps(request, separators=(",", ":")).encode() + b"\x1b\\"
    raw = bytearray()
    try:
        with socket_lib.socket(socket_lib.AF_UNIX, socket_lib.SOCK_STREAM) as client:
            client.settimeout(1.5)
            client.connect(str(socket))
            client.sendall(message)
            while not raw.endswith(b"\x1b\\"):
                chunk = client.recv(65536)
                if not chunk:
                    break
                raw.extend(chunk)
                if len(raw) > 16 * 1024 * 1024:
                    return None
    except (OSError, TimeoutError):
        return None
    prefix = b"\x1bP@kitty-cmd"
    if not raw.startswith(prefix) or not raw.endswith(b"\x1b\\"):
        return None
    try:
        response = json.loads(raw[len(prefix):-2])
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(response, dict) or not response.get("ok"):
        return None
    data = response.get("data")
    return data if isinstance(data, str) else None


def kitty_sockets() -> list[Path]:
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/tmp/kitty-pet-{os.getuid()}"))
    return sorted(path for path in runtime.glob(SOCKET_GLOB) if path.exists())


def position_file(socket: Path, tab_id: int) -> Path:
    key = hashlib.sha256(f"{socket}:{tab_id}".encode()).hexdigest()[:20]
    return POSITION_DIR / f"{key}.json"


def cursor_position(socket: Path, window: dict[str, Any]) -> tuple[int, int] | None:
    """Read only cursor coordinates; screen contents are discarded immediately."""
    output = kitty_socket_request(
        socket,
        "get-text",
        {"match": f"id:{window['id']}", "extent": "screen", "cursor": True},
    )
    if output is None:
        return None
    matches = re.findall(r"\x1b\[(\d+);(\d+)[Hf]", output)
    if not matches:
        return None
    row, column = matches[-1]
    return int(row), int(column)


def read_position(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def update_tab_status(
    socket: Path,
    tab: dict[str, Any],
    source_window: dict[str, Any],
    regular_windows: list[dict[str, Any]],
    config: dict[str, Any],
    query_cursor: bool,
) -> Path:
    target = position_file(socket, int(tab["id"]))
    data = read_position(target)
    coordinates = cursor_position(socket, source_window) if query_cursor else None
    if coordinates is not None:
        row, column = coordinates
        data.update({"row": row, "column": column})

    now = time.time()
    busy = any(window_is_busy(window) for window in regular_windows)
    was_busy = bool(data.get("busy", False))
    if busy:
        state = "running"
        completion_until = 0.0
    elif was_busy:
        exit_codes = [
            int(window["last_cmd_exit_status"])
            for window in regular_windows
            if isinstance(window.get("last_cmd_exit_status"), int)
        ]
        state = "success" if not exit_codes or all(code == 0 for code in exit_codes) else "failed"
        completion_until = now + float(config.get("completion_seconds", 2.5))
    elif now < float(data.get("completion_until", 0.0)):
        state = str(data.get("state", "idle"))
        completion_until = float(data.get("completion_until", 0.0))
    else:
        state = "idle"
        completion_until = 0.0

    data.update(
        {
            "row": int(data.get("row", source_window.get("lines", 1))),
            "column": int(data.get("column", 1)),
            "source_lines": int(source_window.get("lines", data.get("source_lines", 1))),
            "state": state,
            "busy": busy,
            "completion_until": completion_until,
            "updated_at": now,
        }
    )
    atomic_json(target, data, 0o600)
    return target


def launch_pane(
    socket: Path,
    tab: dict[str, Any],
    source_window: dict[str, Any],
    config: dict[str, Any],
    target_position: Path,
) -> int:
    windows = tab.get("windows", [])
    tab_match = f"id:{tab['id']}"
    if len(windows) == 1:
        kitty_socket_command(socket, "goto-layout", "--match", tab_match, "splits")
    bias = max(8, min(25, int(config.get("pane_percent", 13))))
    result = kitty_socket_command(
        socket,
        "launch",
        "--match", tab_match,
        "--source-window", f"id:{source_window['id']}",
        "--type=window",
        "--location=vsplit",
        f"--bias={bias}",
        "--dont-take-focus",
        "--copy-colors",
        "--spacing=padding=2",
        "--env=KITTY_PET_PANE=1",
        f"--env=KITTY_PET_POSITION_FILE={target_position}",
        str(HOME / ".local/bin/kitty-pet"),
        "render",
        capture=True,
    )
    return result.returncode


def close_panes() -> int:
    result = 0
    for socket in kitty_sockets():
        closed = kitty_socket_command(
            socket, "close-window", "--match", "env:KITTY_PET_PANE=1", "--ignore-no-match", capture=True
        )
        result = result or closed.returncode
    return result


def window_is_busy(window: dict[str, Any]) -> bool:
    if window.get("at_prompt") is True:
        return False
    foreground = window.get("foreground_processes")
    if isinstance(foreground, list) and foreground:
        cmdline = foreground[-1].get("cmdline", [])
        if isinstance(cmdline, list) and cmdline:
            executable = Path(str(cmdline[0])).name
            # Without OSC 133, Kitty reports the interactive shell itself at
            # an idle prompt. External and full-screen programs remain busy.
            if executable in {"bash", "dash", "fish", "ksh", "sh", "zsh"}:
                return False
            if executable == "ssh" and any(str(arg).startswith("-t") for arg in cmdline[1:]):
                return False
            return True
    return bool(window.get("in_alternate_screen"))


def controller_iteration() -> None:
    """Discover Kitty state over sockets and maintain one pane per tab."""
    config = load_config()
    enabled = bool(config.get("enabled", False))
    live_positions: set[Path] = set()
    for socket in kitty_sockets():
        listing = kitty_socket_request(socket, "ls", {"output_format": "json"})
        if listing is None:
            continue
        try:
            os_windows = json.loads(listing)
        except json.JSONDecodeError:
            continue
        for os_window in os_windows if isinstance(os_windows, list) else []:
            for tab in os_window.get("tabs", []):
                windows = tab.get("windows", [])
                panes = [window for window in windows if window.get("env", {}).get("KITTY_PET_PANE") == "1"]
                regular = [window for window in windows if window not in panes]
                source_window = next(
                    (window for window in regular if window.get("is_active") or window.get("is_focused")),
                    regular[0] if regular else None,
                )
                target_position = None
                if enabled and source_window is not None:
                    target_position = update_tab_status(
                        socket,
                        tab,
                        source_window,
                        regular,
                        config,
                        bool(tab.get("is_active") or tab.get("is_focused")),
                    )
                    live_positions.add(target_position)
                if enabled and regular and not panes:
                    launch_pane(
                        socket,
                        tab,
                        source_window or regular[0],
                        config,
                        target_position or position_file(socket, int(tab["id"])),
                    )
                elif (not enabled) or (panes and not regular):
                    for pane in panes:
                        kitty_socket_command(
                            socket, "close-window", "--match", f"id:{pane['id']}", "--ignore-no-match", capture=True
                        )
                    if not regular:
                        position_file(socket, int(tab["id"])).unlink(missing_ok=True)

    for path in POSITION_DIR.glob("*.json"):
        if path not in live_positions:
            path.unlink(missing_ok=True)
def controller(once: bool = False) -> int:
    ensure_dirs()
    while True:
        controller_iteration()
        if once:
            return 0
        time.sleep(0.75)


def render_geometry(config: dict[str, Any], position: dict[str, Any]) -> tuple[int, int, int, int]:
    size = os.get_terminal_size(sys.stdout.fileno())
    rows = max(1, min(int(config.get("pet_rows", 7)), size.lines))
    cursor_row = size.lines
    try:
        cursor_row = max(1, int(position.get("row", cursor_row)))
    except (ValueError, TypeError):
        pass
    offset = int(config.get("cursor_offset_rows", 1))
    # row is one-based. Keep the pet's feet just below the cursor and clamp it
    # to the rail so it can never overflow the top or bottom.
    top = cursor_row - rows + offset
    top = max(0, min(top, size.lines - rows))
    return size.columns, size.lines, rows, top


def draw_animation(path: Path, geometry: tuple[int, int, int, int]) -> None:
    columns, _, rows, top = geometry
    subprocess.run(["kitty", "+kitten", "icat", "--clear", "--silent"], check=False)
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()
    subprocess.run(
        [
            "kitty", "+kitten", "icat", "--align=center", f"--place={columns}x{rows}@0x{top}",
            "--scale-up=no", "--loop=-1", "--transfer-mode=stream", str(path),
        ],
        check=False,
    )


def mark_renderer_idle() -> None:
    # Kitty's negative confirm_os_window_close policy excludes windows at a
    # shell-integration prompt. The renderer is always safe to terminate, so
    # mark only its own pane as idle after each graphics update.
    sys.stdout.write("\033]133;A\033\\")
    sys.stdout.flush()


def render() -> int:
    if os.environ.get("TERM") != "xterm-kitty":
        raise PetError("the renderer must run inside Kitty")
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    last_key: tuple[Any, ...] | None = None
    while True:
        config = load_config()
        pet = selected_pet(config)
        enabled = bool(config.get("enabled", True))
        position_path = os.environ.get("KITTY_PET_POSITION_FILE")
        position = read_position(Path(position_path)) if position_path else {}
        state = str(position.get("state") or effective_state(config)) if enabled else "disabled"
        geometry = render_geometry(config, position)
        key = (pet.pet_id, state, enabled, geometry)
        if key != last_key:
            if enabled:
                animation = build_animation(pet, state)
                sys.stdout.write(f"\033]2;Terminal Pet: {pet.display_name} ({state})\007")
                sys.stdout.flush()
                draw_animation(animation, geometry)
                mark_renderer_idle()
            else:
                subprocess.run(["kitty", "+kitten", "icat", "--clear", "--silent"], check=False)
                sys.stdout.write("\033[2J\033[H\033]2;Terminal Pet: paused\007")
                mark_renderer_idle()
            last_key = key
        time.sleep(0.2)


def select_command(pet_id: str | None) -> int:
    config = load_config()
    pets = discover_pets(config)
    if not pets:
        raise PetError(f"no pets found under {', '.join(config['pet_roots'])}")
    ordered = sorted(pets.values(), key=lambda pet: pet.display_name.casefold())
    if pet_id is None:
        if not sys.stdin.isatty():
            raise PetError("specify a pet id when not running interactively")
        print("Select a terminal pet:\n")
        for index, pet in enumerate(ordered, 1):
            marker = "*" if pet.pet_id == config.get("pet") else " "
            print(f" {marker} {index:2}. {pet.display_name} ({pet.pet_id})")
        print()
        try:
            answer = input("Pet number or id (blank cancels): ").strip()
        except EOFError:
            return 1
        if not answer:
            return 0
        if answer.isdigit() and 1 <= int(answer) <= len(ordered):
            pet_id = ordered[int(answer) - 1].pet_id
        else:
            pet_id = answer
    if pet_id not in pets:
        raise PetError(f"unknown pet {pet_id!r}; run 'kitty-pet list' to see available pets")
    config["pet"] = pet_id
    config["enabled"] = True
    save_config(config)
    for state in ("idle", "running", "success", "failed", "waiting"):
        build_animation(pets[pet_id], state)
    print(f"Selected {pets[pet_id].display_name}. Existing pet panes will update automatically.")
    return 0


def list_command() -> int:
    config = load_config()
    pets = discover_pets(config)
    for pet in sorted(pets.values(), key=lambda item: item.display_name.casefold()):
        marker = "*" if pet.pet_id == config.get("pet") else " "
        print(f"{marker} {pet.pet_id:<16} {pet.display_name}")
    return 0


def status_command() -> int:
    config = load_config()
    pet = selected_pet(config)
    print(f"Pet: {pet.display_name} ({pet.pet_id})")
    print(f"Enabled: {'yes' if config.get('enabled', True) else 'no'}")
    print(f"Effective state: {effective_state(config)}")
    print(f"Registry: {pet.directory}")
    print(f"Configuration: {CONFIG_FILE}")
    return 0


def self_test() -> int:
    config = load_config()
    pets = discover_pets(config)
    if not pets:
        raise PetError("no usable pets discovered")
    for pet in pets.values():
        with Image.open(pet.sheet) as image:
            expected = (pet.frame["width"] * pet.frame["columns"], pet.frame["height"] * pet.frame["rows"])
            if image.size != expected:
                raise PetError(f"{pet.pet_id}: invalid sheet dimensions {image.size}, expected {expected}")
    pet = selected_pet(config)
    outputs = [build_animation(pet, state) for state in ("idle", "running", "success", "failed", "waiting")]
    for output in outputs:
        with Image.open(output) as animation:
            if getattr(animation, "n_frames", 0) < 1:
                raise PetError(f"empty animation cache: {output}")
    print(f"Self-test passed: {len(pets)} pets discovered; {pet.display_name} animations are ready.")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="kitty-pet", description=__doc__)
    result.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list pets from the shared Codex/Petdex registry")
    choose = commands.add_parser("select", help="select a pet interactively or by id")
    choose.add_argument("pet_id", nargs="?")
    controller_parser = commands.add_parser("controller", help=argparse.SUPPRESS)
    controller_parser.add_argument("--once", action="store_true")
    commands.add_parser("close", help="close all managed pet panes")
    commands.add_parser("render", help=argparse.SUPPRESS)
    state = commands.add_parser("state", help="set task state for advanced integrations")
    state.add_argument("kind", choices=["idle", "running", "done", "success", "failed", "waiting"])
    state.add_argument("pid", type=int)
    state.add_argument("exit_code", type=int, nargs="?", default=0)
    commands.add_parser("status", help="show the selected pet and aggregate task state")
    commands.add_parser("enable", help="enable pet rendering")
    commands.add_parser("disable", help="pause pet rendering without closing panes")
    commands.add_parser("toggle", help="toggle pet rendering")
    commands.add_parser("self-test", help="validate assets and generated animations")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.command == "list":
        return list_command()
    if args.command == "select":
        return select_command(args.pet_id)
    if args.command == "controller":
        return controller(args.once)
    if args.command == "close":
        return close_panes()
    if args.command == "render":
        return render()
    if args.command == "state":
        write_state(args.kind, args.pid, args.exit_code)
        return 0
    if args.command == "status":
        return status_command()
    if args.command in {"enable", "disable", "toggle"}:
        config = load_config()
        if args.command == "enable":
            config["enabled"] = True
        elif args.command == "disable":
            config["enabled"] = False
        else:
            config["enabled"] = not bool(config.get("enabled", True))
        save_config(config)
        print(f"Terminal pets {'enabled' if config['enabled'] else 'paused'}.")
        return 0
    if args.command == "self-test":
        return self_test()
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PetError as exc:
        print(f"kitty-pet: {exc}", file=sys.stderr)
        raise SystemExit(1)
