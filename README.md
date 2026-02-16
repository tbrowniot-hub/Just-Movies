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
python -m MovieRipper import-master --csv ".\MASTEREXPORT.csv" --out ".\MovieRipper\movie_index.json"
python -m MovieRipper build-queue --index ".\MovieRipper\movie_index.json" --out ".\MovieRipper\movie_queue.json"
python -m MovieRipper run-queue   --queue ".\MovieRipper\movie_queue.json" --config ".\config.json"
```

Behavior remains: rip to a staging root, wait for idle finalization, then move/rename to a final root.

## Setup

```powershell
python -m pip install -e .
```

Optional console script:

```powershell
movieripper --help
```

`python -m MovieRipper ...` continues to work.


## Default locations

`config.json` now supports explicit defaults for the two pipeline stages:

- `rips_staging_root`: where each rip job folder is created and MakeMKV writes initial output.
- `final_movies_root`: where the final keeper MKV is moved after successful processing.

Backward-compatible aliases are still accepted when loading config:

- `rip_prep_root` is treated as `rips_staging_root`
- `rip_staging_root` is treated as `final_movies_root`

CLI path arguments keep existing behavior and still override defaults when provided.

## Config

1. Copy `config.example.json` to `config.json`.
2. Update values for your machine.
3. See full field reference in `docs/configuration.md`.

Config discovery order:
1. `--config` when provided
2. `MOVIERIPPER_CONFIG`
3. `./config.json`
4. `~/.movieripper/config.json`

Helpful commands:

```powershell
movieripper config where
movieripper config init --path ".\config.json"
```

## Runtime artifacts (not committed)

These files are generated during local runs and are intentionally gitignored:
- `MovieRipper/movie_index.json`
- `MovieRipper/movie_queue.json`
- Python bytecode (`__pycache__/`, `*.pyc`)

`movie_index.json` and `movie_queue.json` stay at the same default paths used by CLI scripts and the Web UI.

## Web UI

```powershell
python -m pip install -e .
python -m pip install -e ".[web]"
python -m MovieRipper web --host 127.0.0.1 --port 8765
```

Security note: default host is localhost (`127.0.0.1`). Use `--host 0.0.0.0` only when you intentionally want LAN exposure.

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
