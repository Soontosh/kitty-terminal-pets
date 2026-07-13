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

Please do not add copyrighted character artwork to the repository. Compatibility code and manifests are welcome; users can install third-party art separately under its own terms.

Pull requests run the install and runtime test suite on both Ubuntu and macOS. Platform-specific service changes should keep the systemd and launchd paths idempotent.
