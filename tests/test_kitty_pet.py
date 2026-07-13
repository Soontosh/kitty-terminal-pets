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

    def test_timing_overrides_resolve_down_to_each_frame(self) -> None:
        pet = kitty_pet.discover_pets(self.config())["byte-cat"]
        config = {
            **self.config(),
            "timings": {
                "speed": 2,
                "states": {"running": {"fps": 5}},
                "pets": {
                    "byte-cat": {
                        "speed": 0.5,
                        "states": {"running": {"frame_ms": [100, 110, 120, 130, 140, 150]}},
                    }
                },
            },
        }
        frames, durations = kitty_pet.animation_spec(pet, "running", config)
        self.assertEqual([56, 57, 58, 59, 60, 61], frames)
        self.assertEqual([200, 220, 240, 260, 280, 300], durations)

    def test_timing_can_vary_completion_display_by_pet_and_state(self) -> None:
        config = {
            **self.config(),
            "completion_seconds": 2.5,
            "timings": {
                "display_seconds": 3,
                "states": {"failed": {"display_seconds": 4}},
                "pets": {
                    "byte-cat": {
                        "display_seconds": 5,
                        "states": {"failed": {"display_seconds": 6}},
                    }
                },
            },
        }
        self.assertEqual(5, kitty_pet.display_seconds(config, "byte-cat", "success"))
        self.assertEqual(6, kitty_pet.display_seconds(config, "byte-cat", "failed"))
        self.assertEqual(4, kitty_pet.display_seconds(config, "another-pet", "failed"))

    def test_rejects_bad_per_frame_timing(self) -> None:
        pet = kitty_pet.discover_pets(self.config())["byte-cat"]
        config = {
            **self.config(),
            "timings": {
                "pets": {"byte-cat": {"states": {"running": {"frame_ms": [100, 200]}}}}
            },
        }
        with self.assertRaisesRegex(kitty_pet.PetError, "has 6 frames"):
            kitty_pet.animation_spec(pet, "running", config)

    def test_timing_command_writes_a_scoped_override(self) -> None:
        config = self.config()
        pets = kitty_pet.discover_pets(config)
        output = io.StringIO()
        with (
            mock.patch.object(kitty_pet, "load_config", return_value=config),
            mock.patch.object(kitty_pet, "discover_pets", return_value=pets),
            mock.patch.object(kitty_pet, "save_config") as save,
            redirect_stdout(output),
        ):
            result = kitty_pet.timing_command("byte-cat", "running", 4, None, None, None, False)
        self.assertEqual(0, result)
        self.assertEqual(4, config["timings"]["pets"]["byte-cat"]["states"]["running"]["fps"])
        save.assert_called_once_with(config)

    def test_completion_duration_changes_apply_to_an_existing_pose(self) -> None:
        target = Path(TEMP_ROOT.name) / "completion.json"
        config = {
            **self.config(),
            "timings": {"pets": {"byte-cat": {"states": {"success": {"display_seconds": 8}}}}},
        }
        tab = {"id": 7}
        window = {"id": 9, "lines": 30, "at_prompt": True, "last_cmd_exit_status": 0}
        with (
            mock.patch.object(kitty_pet, "position_file", return_value=target),
            mock.patch.object(kitty_pet, "read_position", return_value={"busy": True}),
            mock.patch.object(kitty_pet.time, "time", return_value=100),
        ):
            kitty_pet.update_tab_status(Path("/tmp/fake.sock"), tab, window, [window], config, False)

        completed = kitty_pet.read_position(target)
        self.assertEqual("success", completed["state"])
        self.assertEqual(108, completed["completion_until"])

        config["timings"]["pets"]["byte-cat"]["states"]["success"]["display_seconds"] = 2
        with (
            mock.patch.object(kitty_pet, "position_file", return_value=target),
            mock.patch.object(kitty_pet.time, "time", return_value=103),
        ):
            kitty_pet.update_tab_status(Path("/tmp/fake.sock"), tab, window, [window], config, False)
        self.assertEqual("idle", kitty_pet.read_position(target)["state"])

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
