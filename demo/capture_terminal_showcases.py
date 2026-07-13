#!/usr/bin/env python3
"""Capture the real local Kitty setup through every visible pet state.

This is a maintainer tool, not part of installation. It launches an isolated
X11/XWayland Kitty window so ImageMagick can capture the genuine terminal
theme without reading from or injecting input into the user's active TTY.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "assets" / "examples"
PETS = ("killua", "luffy", "kid-obito", "tobirama")
FRAME_SECONDS = 0.15
WINDOW_WIDTH = 1214
WINDOW_HEIGHT = 686


def executable(name: str, fallback: str | None = None) -> str:
    found = shutil.which(name)
    if found:
        return found
    if fallback and Path(fallback).is_file():
        return fallback
    raise SystemExit(f"Required command not found: {name}")


KITTY = executable("kitty", str(Path.home() / ".local/kitty.app/bin/kitty"))
KITTEN = executable("kitten", str(Path.home() / ".local/kitty.app/bin/kitten"))
KITTY_PET = executable("kitty-pet", str(Path.home() / ".local/bin/kitty-pet"))
IMPORT = executable("import")
CONVERT = executable("convert")


def run(*args: str, **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=True, text=True, **kwargs)


def remote(socket: Path, *args: str, input_text: str | None = None) -> None:
    run(
        KITTEN,
        "@",
        "--to",
        f"unix:{socket}",
        *args,
        input=input_text,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_for_socket(socket: Path, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if socket.exists():
            return
        if process.poll() is not None:
            raise RuntimeError("Kitty exited before its control socket appeared")
        time.sleep(0.04)
    raise RuntimeError(f"Timed out waiting for {socket}")


def window_details(socket: Path) -> tuple[int, int]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            result = run(
                KITTEN,
                "@",
                "--to",
                f"unix:{socket}",
                "ls",
                capture_output=True,
            )
            os_window = json.loads(result.stdout)[0]
            main_window = os_window["tabs"][0]["windows"][0]
            return int(os_window["platform_window_id"]), int(main_window["id"])
        except (IndexError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError):
            time.sleep(0.04)
    raise RuntimeError("Kitty did not expose its demo window")


def type_slowly(socket: Path, window_id: int, text: str, delay: float) -> None:
    for character in text:
        remote(
            socket,
            "send-text",
            "--match",
            f"id:{window_id}",
            "--stdin",
            input_text=character,
        )
        time.sleep(delay)


def press_enter(socket: Path, window_id: int) -> None:
    remote(
        socket,
        "send-text",
        "--match",
        f"id:{window_id}",
        "--stdin",
        input_text="\r",
    )


def capture_frames(
    platform_window_id: int,
    frame_dir: Path,
    stop: threading.Event,
) -> None:
    frame = 0
    deadline = time.monotonic()
    while not stop.is_set():
        subprocess.run(
            [IMPORT, "-window", str(platform_window_id), str(frame_dir / f"{frame:04d}.png")],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        frame += 1
        deadline += FRAME_SECONDS
        stop.wait(max(0, deadline - time.monotonic()))


def capture_pet(pet: str, work_dir: Path) -> None:
    print(f"Capturing {pet}…", flush=True)
    run(KITTY_PET, "select", pet, stdout=subprocess.DEVNULL)
    time.sleep(1.1)

    socket = Path(os.environ.get("XDG_RUNTIME_DIR", f"/tmp/kitty-pet-{os.getuid()}")) / f"kitty-pet-showcase-{pet}.sock"
    socket.unlink(missing_ok=True)
    frame_dir = work_dir / pet
    frame_dir.mkdir()

    env = os.environ.copy()
    env["KITTY_DISABLE_WAYLAND"] = "1"
    process = subprocess.Popen(
        [
            KITTY,
            "--listen-on",
            f"unix:{socket}",
            "--title",
            f"Kitty Terminal Pets — {pet}",
            "--override",
            "remember_window_size=no",
            "--override",
            f"initial_window_width={WINDOW_WIDTH}",
            "--override",
            f"initial_window_height={WINDOW_HEIGHT}",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    stop = threading.Event()
    capture_thread: threading.Thread | None = None
    try:
        wait_for_socket(socket, process)
        platform_window_id, main_window_id = window_details(socket)
        capture_thread = threading.Thread(
            target=capture_frames,
            args=(platform_window_id, frame_dir, stop),
            daemon=True,
        )
        capture_thread.start()

        # Startup: first the prompt, then the controller adds the pet rail.
        time.sleep(2.2)

        # Typing -> running -> success.
        type_slowly(socket, main_window_id, 'sleep 2 && echo "✓ command succeeded"', 0.075)
        time.sleep(0.35)
        press_enter(socket, main_window_id)
        time.sleep(4.8)

        # A shorter second run finishes nonzero and exposes the failed state.
        type_slowly(socket, main_window_id, 'sleep 1; echo "✗ command failed"; false', 0.025)
        time.sleep(0.25)
        press_enter(socket, main_window_id)
        time.sleep(4.0)
    finally:
        stop.set()
        if capture_thread:
            capture_thread.join(timeout=3)
        try:
            remote(socket, "quit")
        except subprocess.CalledProcessError:
            process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        socket.unlink(missing_ok=True)

    frames = sorted(frame_dir.glob("*.png"))
    if len(frames) < 40:
        raise RuntimeError(f"Only captured {len(frames)} frames for {pet}")
    output = OUTPUT_DIR / f"{pet}.gif"
    run(
        CONVERT,
        "-delay",
        str(round(FRAME_SECONDS * 100)),
        "-loop",
        "0",
        *map(str, frames),
        "-alpha",
        "off",
        "-layers",
        "Optimize",
        str(output),
    )
    if pet == "killua":
        shutil.copyfile(output, ROOT / "demo" / "killua-riced-kitty.gif")
    print(f"Wrote {output.relative_to(ROOT)} ({len(frames)} frames)", flush=True)


def selected_pet() -> str:
    config = Path.home() / ".config/kitty-pet/config.json"
    try:
        return str(json.loads(config.read_text())["pet"])
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return "byte-cat"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "pets",
        nargs="*",
        choices=PETS,
        metavar="PET",
        help="capture only these pets (default: all four)",
    )
    args = parser.parse_args()
    if not os.environ.get("DISPLAY"):
        raise SystemExit("A graphical X11/XWayland session is required")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    original_pet = selected_pet()
    try:
        with tempfile.TemporaryDirectory(prefix="kitty-pet-showcases-") as temporary:
            for pet in args.pets or PETS:
                capture_pet(pet, Path(temporary))
    finally:
        run(KITTY_PET, "select", original_pet, stdout=subprocess.DEVNULL)
    print(f"Restored selected pet: {original_pet}")


if __name__ == "__main__":
    main()
