# Agent Guide

## Goal

Complete the Patrick's Parabox demo from local game state using only basic
observation and input tools. The target end state is:

- every demo level in the save file is marked `1 1`
- the player can reach the demo end area in the hub

Do not use network access during the challenge unless the user explicitly allows it.

## Safety Rules

- Confirm the player position before every keypress.
- Use patched log state for player position checks.
- If the game is launched or restarted and opens on the menu, press Enter once before navigating.
- The demo save file may not exist until at least one level has been completed.
- Do not blindly continue after a mismatch. Stop, read the log, and either resume from the correct step or recompute from the confirmed state.
- Do not use solver, route-finder, replay, or recorded route scripts for a fresh challenge.
- Treat `local_challenge_artifacts/` as off-limits unless the user explicitly says to use local private scripts.

## Setup

Install or inspect the state logger patch:

```bash
python3 scripts/install_patrick_patch.py --status
python3 scripts/install_patrick_patch.py --install --live-blocks
```

Start or restart the game after patching. Confirm logging:

```bash
python3 scripts/patrick_send_keys.py enter
python3 scripts/read_patrick_state_log.py
python3 scripts/read_patrick_live_blocks.py
```

Only send Enter if the game is on the menu. If logging already shows a playable
level, read the current position and continue from there.

If the output does not contain a level and `x/y` coordinates, make sure the game is running in a playable state and that the patch is installed.

## Coordinate Frames

Public tools default to screen coordinates. These coordinates match the visible
board and physical movement:

- press up: `y - 1`
- press down: `y + 1`
- press left: `x - 1`
- move right: `x + 1`

`read_patrick_state_log.py` prints `coords=screen` plus `raw_x/raw_y` for
debugging. `read_patrick_levels.py` also renders screen coordinates by default.
Use `--coords raw` only when inspecting Unity asset data.

`patrick_send_keys.py` accepts physical key names. It does not confirm positions
or solve movement by itself. In this desktop setup, `d` is the most reliable
right-move key.

## Movement Rules

Pushing can propagate through a straight line of pushable blocks when every
block in the chain has room to move into the next cell. Treat chain push as
normal game physics, not as a level-specific trick.

## Core Commands

Read the current state:

```bash
python3 scripts/read_patrick_state_log.py
```

Read the current player cell and all live non-player block cells in the same
outer board:

```bash
python3 scripts/read_patrick_live_blocks.py
```

If this prints `blocks=0` in a puzzle that visibly has non-player blocks, the
game is probably still running an older DLL in memory. Restart the game after
installing `--live-blocks`, then press Enter if it opens on the menu.

The `block id` in live output is the runtime `DebugID`. It may differ from the
asset `block_id` printed by `read_patrick_blocks.py`; match blocks by current
cell, initial cell, and interaction type instead of assuming the ids are equal.

`read_patrick_live_blocks.py` intentionally does not report static wall blocks.
Use `read_patrick_levels.py --level LEVEL_NAME` for walls, buttons, portals, and
other initial terrain, then combine that static map with live player/block cells.

Render a level:

```bash
python3 scripts/read_patrick_levels.py --level LEVEL_NAME
```

Inspect hub portals:

```bash
python3 scripts/read_patrick_hub.py
```

`read_patrick_hub.py` reports `enterable`, `completed`, or `locked`. If it prints
`save=not-found`, remember that the game normally creates `save_demoN.txt` only
after at least one level is completed.

Inspect block interaction inside a level:

```bash
python3 scripts/read_patrick_blocks.py --level LEVEL_NAME
```

`interaction=enterable` means the block has an open edge and can be entered.
`interaction=push-only` means it has no open edge and should be treated as a
pushable block.
`interaction=controlled-player` is the current player object. Do not enter or
push it. Do not infer enterability from color; yellow-looking blocks can be
push-only, and the current player may appear as another color. Use the
`interaction`, `enterable`, and `pushable` fields.

`read_patrick_blocks.py` and `read_patrick_levels.py` report initial asset
positions. Always use `read_patrick_state_log.py` for the current player
position before pressing a key. Use `read_patrick_live_blocks.py` after pushes
to refresh the current cells for non-player blocks in the same outer board.

Every block occupies one cell in its parent board. A block's `inner_size`, such
as `5x5`, describes the board inside that block if it is enterable; it is not a
5-by-5 outer footprint. Do not model blocks as overlapping rectangles on the
outer board. The `x/y` from `read_patrick_state_log.py` is the current avatar's
cell in the current level, not a hidden local coordinate inside the player block.

Preview key parsing without sending input:

```bash
python3 scripts/patrick_send_keys.py "down,right" --dry-run
```

Send a single physical key after confirming the current player position:

```bash
python3 scripts/patrick_send_keys.py down
```

Return to the previous map layer when stuck in a puzzle:

```bash
python3 scripts/patrick_send_keys.py "escape,down,enter" --delay 0.35
python3 scripts/read_patrick_state_log.py
```

Check save and hub progress:

```bash
python3 scripts/read_patrick_hub.py
```

## Recommended Strategy

1. Confirm current level and position from `Player.log`.
2. If in the hub, use `read_patrick_hub.py` to distinguish enterable, completed, and locked portals; choose the next portal manually.
3. If in a puzzle, render or inspect the level, then use `read_patrick_blocks.py` to tell enterable blocks from push-only blocks. Treat `controlled-player` as the current avatar, not a target block, and treat every block as occupying one parent-board cell.
4. Before every keypress, read the state and verify that the player is where expected.
5. Use `read_patrick_live_blocks.py` whenever non-player block positions matter.
6. Send only the intended key or a very short intentional sequence.
7. After each action, read the state again and update the mental model.
8. If a move is missed or double-fires, stop, read the confirmed state, and continue from that state.
9. If the puzzle state is no longer useful, use `escape,down,enter` with delay to return to the previous map layer, then read the log before moving.

## Tool Boundaries

Reusable tools to keep:

- patch/install/status/restore scripts
- log readers
- asset parsers
- hub status readers
- block interaction readers
- key input wrappers
- coordinate conversion helpers

Artifacts to keep out of a fresh challenge:

- solver scripts
- hub route-finder scripts
- automatic play/replay scripts
- screenshot-based position detectors
- level-specific one-off solvers
- recorded full solution routes
- local screenshots/log dumps
- compiled binaries and Python caches
- machine-local config files

These local-only artifacts belong in `local_challenge_artifacts/`, which is
ignored and should not be included when handing the project to a fresh agent.

## Recovery

Restore the game DLL:

```bash
python3 scripts/install_patrick_patch.py --restore
```

Restart the game afterward.

If stuck inside a puzzle, return to the previous map layer:

```bash
python3 scripts/patrick_send_keys.py "escape,down,enter" --delay 0.35
python3 scripts/read_patrick_state_log.py
```

If automated input stops working, check macOS Accessibility and Automation permissions for the terminal or agent process.
