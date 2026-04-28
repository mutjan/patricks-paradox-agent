# Patrick's Parabox Tooling

This directory contains only reusable public tools. They should help an agent
observe state and perform basic input, but should not provide routes or solve
puzzles for it.

## Keep: reusable tools

- `inspect_dotnet_metadata.py`: inspect and disassemble the Unity/.NET assembly.
- `install_patrick_patch.py`: public install/status/restore wrapper for the game DLL logger patch.
- `patch_patrick_state_logger.py`: patch the game to log current player and optional live block positions.
- `patrick_config.py`: shared local config loader.
- `patrick_coords.py`: raw/screen coordinate conversion and input-direction mapping.
- `patrick_send_keys.py`: activate the game and send movement keys.
- `patrick_cgevent_keys.c`: CoreGraphics key-event helper source.
- `read_patrick_levels.py`: extract and render level layouts from `resources.assets`; defaults to screen coordinates.
- `read_patrick_state_log.py`: read the latest patched state line from `Player.log`; defaults to screen coordinates.
- `read_patrick_live_blocks.py`: read the latest player cell plus live non-player block cells from `Player.log`.
- `read_patrick_hub.py`: list hub portals as enterable, completed, or locked.
- `read_patrick_blocks.py`: list level blocks as enterable, push-only, or controlled-player.

## Moved out: solver, route, replay, or local artifacts

Non-delivered challenge scripts live in `../local_challenge_artifacts/`, which is
ignored by `.gitignore`.

- `patrick_play_level.py`: automatically solves or replays level move lists.
- `patrick_walk_moves.py`: executes a supplied route and can replay recorded paths.
- `route_patrick_map.py`: computes hub routes to portals.
- `read_patrick_screen_position.py`: screenshot-based fallback position detector.
- `solve_correct_outer.py`: one-off macro solver for the `correct_placement` outer layer.
- `solve_patrick_recursive.py`: recursive movement solver for nested mechanics.
- `solve_patrick_simple.py`: simple Sokoban-style solver for flat levels.
- `patrick_cgevent_keys`: compiled binary generated from `patrick_cgevent_keys.c`.
- `__pycache__/` and `*.pyc`: Python cache output.
- `patrick_config.json`: local app/input configuration.
- screenshots/logs/scratch scripts created during a run.
- future `solve_*`, `route_*`, `*replay*`, `*play_level`, and `*walk_moves` scripts.

If a future agent is meant to solve the demo from scratch, give it the reusable
tools above plus `patrick_config.example.json`, but do not give it solver,
route-finder, replay, level-specific scratch, or recorded solution scripts.
