from __future__ import annotations

import importlib.util
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TEMP_ROOT = tempfile.TemporaryDirectory()
os.environ["HOME"] = TEMP_ROOT.name
os.environ["XDG_CONFIG_HOME"] = str(Path(TEMP_ROOT.name) / "config")
os.environ["XDG_CACHE_HOME"] = str(Path(TEMP_ROOT.name) / "cache")
os.environ["XDG_RUNTIME_DIR"] = str(Path(TEMP_ROOT.name) / "runtime")

spec = importlib.util.spec_from_file_location("kitty_pet", ROOT / "src" / "kitty_pet.py")
assert spec and spec.loader
kitty_pet = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = kitty_pet
spec.loader.exec_module(kitty_pet)


class PetTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls) -> None:
        TEMP_ROOT.cleanup()

    def config(self) -> dict:
        return {
            **kitty_pet.DEFAULT_CONFIG,
            "pet": "byte-cat",
            "pet_roots": [str(ROOT / "assets")],
        }

    def test_discovers_bundled_pet(self) -> None:
        pets = kitty_pet.discover_pets(self.config())
        self.assertEqual(["byte-cat"], list(pets))
        self.assertEqual("Byte Cat", pets["byte-cat"].display_name)

    def test_animation_is_valid_and_loops_forever(self) -> None:
        pet = kitty_pet.discover_pets(self.config())["byte-cat"]
        target = kitty_pet.build_animation(pet, "running")
        self.assertTrue(target.is_file())

        with kitty_pet.Image.open(target) as animation:
            self.assertEqual((192, 208), animation.size)
            self.assertEqual(6, animation.n_frames)
            self.assertEqual(0, animation.info.get("loop"))

    def test_sprite_atlas_has_expected_dimensions(self) -> None:
        with kitty_pet.Image.open(ROOT / "assets" / "byte-cat" / "spritesheet.webp") as sheet:
            self.assertEqual((1536, 1872), sheet.size)

    def test_pet_tracks_cursor_without_overflow(self) -> None:
        config = {**self.config(), "pet_rows": 7, "cursor_offset_rows": 1}
        terminal_size = os.terminal_size((26, 37))
        with mock.patch.object(kitty_pet.os, "get_terminal_size", return_value=terminal_size):
            self.assertEqual((26, 37, 7, 0), kitty_pet.render_geometry(config, {"row": 1}))
            self.assertEqual((26, 37, 7, 8), kitty_pet.render_geometry(config, {"row": 14}))
            self.assertEqual((26, 37, 7, 30), kitty_pet.render_geometry(config, {"row": 99}))

    def test_busy_detection_ignores_idle_shell_and_interactive_ssh(self) -> None:
        self.assertFalse(kitty_pet.window_is_busy({"at_prompt": True}))
        self.assertFalse(
            kitty_pet.window_is_busy(
                {"foreground_processes": [{"cmdline": ["/usr/bin/bash"]}]}
            )
        )
        self.assertFalse(
            kitty_pet.window_is_busy(
                {"foreground_processes": [{"cmdline": ["ssh", "-t", "example.test"]}]}
            )
        )
        self.assertTrue(
            kitty_pet.window_is_busy(
                {"foreground_processes": [{"cmdline": ["sleep", "20"]}]}
            )
        )

    def test_renderer_marks_only_its_pane_idle(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            kitty_pet.mark_renderer_idle()
        self.assertEqual("\x1b]133;A\x1b\\", output.getvalue())


if __name__ == "__main__":
    unittest.main()
