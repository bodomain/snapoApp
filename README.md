# Snapo

Snapo is a local PySide6 desktop productivity timer with Pomodoro-style cycles,
SQLite session tracking, sounds, and a compact productivity dashboard.

## Features

- Custom work, short break, long break, cycle count, activity, and comment.
- Standard and endless sessions.
- Pause, resume, log-and-stop, and cancel controls.
- Local SQLite history in `prodz.db`.
- Dashboard with recent sessions and daily activity bars.
- Optional Git database sync via the in-app `Git-Sync` checkbox.
- PyInstaller configuration for a standalone desktop build.

## Run From Source

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

## Build Standalone App

```bash
pyinstaller snapo.spec
./dist/snapo/snapo
```

The build bundles `bell.wav`, `coin.wav`, and the current `prodz.db`. The
private key file in this repository is not used by the app or the build config.

## CLI Compatibility

The original command-line entry point is still available:

```bash
python3 prodz_cli.py
```

The desktop app is the primary interface. Database access is local by default;
Git sync only runs when explicitly enabled in the desktop app.

## Files

- `app.py`: PySide6 desktop app.
- `timer_engine.py`: GUI-independent timer/session state.
- `database.py`: SQLite storage and optional Git sync.
- `plot.py`: Shared productivity summary plus CLI chart output.
- `snapo.spec`: PyInstaller build configuration.
# snapoApp
