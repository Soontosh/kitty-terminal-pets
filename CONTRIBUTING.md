# Contributing

Issues and small PRs are very welcome. This is a terminal pet project; being friendly is part of the feature set.

## Local checks

```bash
python3 -m pip install Pillow
python3 -m unittest discover -s tests -v
bash tests/smoke.sh
```

Regenerate Byte Cat and the demo with:

```bash
python3 demo/generate_assets.py
```

The four real-terminal showcase loops are captured separately on the original
development machine. With Kitty Terminal Pets running, ImageMagick installed,
and the Petdex pets available locally, run:

```bash
python3 demo/capture_terminal_showcases.py
```

The tool uses an isolated Kitty control socket, restores the selected pet when
it finishes, and records startup, slow typing, running, success, and failure.

Please do not add copyrighted character artwork to the repository. Compatibility code and manifests are welcome; users can install third-party art separately under its own terms.

Pull requests run the install and runtime test suite on both Ubuntu and macOS. Platform-specific service changes should keep the systemd and launchd paths idempotent.
