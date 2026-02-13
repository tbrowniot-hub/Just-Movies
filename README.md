# MovieRipper

Queue-driven Windows movie ripping helper.

## Repository layout

- `MovieRipper/` package code
- `scripts/` PowerShell helper scripts
- `docs/` project docs
- `tests/` minimal tests

## Non-breaking commands

These existing commands are preserved:

```powershell
python -m MovieRipper build-queue --index ".\MovieRipper\movie_index.json" --out ".\MovieRipper\movie_queue.json"
python -m MovieRipper run-queue   --queue ".\MovieRipper\movie_queue.json"
```

Behavior remains: rip to `RIP_PREP`, wait for idle finalization, then move/rename to `RIPS_STAGING`.

## Setup

```powershell
python -m pip install -e .
```

Optional console script:

```powershell
movieripper --help
```

`python -m MovieRipper ...` continues to work.

## Config

1. Copy `config.example.json` to `config.json`.
2. Update values for your machine.
3. See full field reference in `docs/configuration.md`.

## Smoke test (no disc required)

```powershell
python -m MovieRipper smoke-test --config ".\config.json"
```

Checks:
- configured path existence
- MakeMKV path existence
- package load path (`MovieRipper.__file__`)

## Scripts

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\01_build_queue.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\02_run_queue.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\03_eject.ps1 -DriveLetter "D:"
```
