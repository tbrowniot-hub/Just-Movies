# Configuration Reference

All settings are read from `config.json` (copy from `config.example.json`).

- `rip_prep_root`: Temporary rip output root. Each queue item writes all raw MKVs here first.
- `rip_staging_root`: Final staging root for renamed keeper files.
- `makemkv_cmd`: Full path (recommended) or command name for `makemkvcon64.exe`.
- `disc_spec`: MakeMKV disc selector, usually `disc:0`.
- `makemkv_minlength_seconds`: Passed to MakeMKV `--minlength`.
- `auto_eject`: If true, request eject after each successful move to staging.
- `min_minutes_main`: Minimum duration for keeper selection.
- `idle_seconds`: Folder-idle threshold before finalize/move step.
- `ffprobe_cmd`: Full path or command name for `ffprobe`.
- `move_mode`: `move` (default) or `copy` for keeper transfer to staging.
- `keeper_policy`: Keeper selection controls:
  - `prefer_angle_1_if_labeled`
  - `duration_tolerance_seconds`
- `log_dir`: Reserved log folder path for operational logs/scripts.
- `drive_letter`: Optical drive letter for media fallback checks and COM eject (default `D:`).
