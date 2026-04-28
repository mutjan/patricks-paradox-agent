# Patrick Parodex

Patrick Parodex is a small local toolkit for agents that want to attempt the Patrick's Parabox demo on macOS. It provides three practical layers:

- a reversible patch that makes the Unity game write live grid coordinates to `Player.log`
- read-only helpers for inspecting current state and level data
- basic input helpers for sending game keys

The public toolkit is intentionally limited: it should help an agent see the board
and operate the game, but it should not hand over routes or puzzle solutions. The
project is intended for local automation and research. It does not require network
access.

## Requirements

- macOS
- Patrick's Parabox Demo installed locally, usually through Steam
- Python 3.11 or newer
- Xcode Command Line Tools, for compiling the CoreGraphics key-event helper when needed
- macOS Accessibility and Automation permissions for the terminal or agent process that sends keys

The default workflow uses the log patch instead of screenshots.

## Installation

1. Clone or copy this repository.

2. Create local configuration if needed:

   ```bash
   cp patrick_config.example.json patrick_config.json
   ```

   `patrick_config.json` is ignored by git. The default config is usually enough:

   ```json
   {
     "app_name": "Patrick's Parabox",
     "input_delay": 0.07
   }
   ```

3. Quit Patrick's Parabox before patching the game assembly.

4. Install the live-state logger patch:

   ```bash
   python3 scripts/install_patrick_patch.py --install --live-blocks
   ```

   If Steam installed the game somewhere unusual, pass the assembly path explicitly:

   ```bash
   python3 scripts/install_patrick_patch.py --install --live-blocks --assembly "/path/to/Assembly-CSharp.dll"
   ```

5. Check patch status:

   ```bash
   python3 scripts/install_patrick_patch.py --status
   ```

6. Start the game. If it opens on the menu after launch or restart, press Enter
   once to enter the game:

   ```bash
   python3 scripts/patrick_send_keys.py enter
   ```

7. Verify that state logging works:

   ```bash
   python3 scripts/read_patrick_state_log.py
   python3 scripts/read_patrick_live_blocks.py
   ```

   A healthy output looks like:

   ```text
   level=hub
   area=Area_Enter
   state=
   coords=screen
   x=...
   y=...
   raw_x=...
   raw_y=...
   ```

## Restoring the Game Assembly

The installer creates a backup next to the patched assembly:

```text
Assembly-CSharp.dll.patrick_state_logger.bak
```

To restore the original DLL:

```bash
python3 scripts/install_patrick_patch.py --restore
```

Restart the game after restoring.

## Common Workflow

Read the current logged state:

```bash
python3 scripts/read_patrick_state_log.py
```

Read the current player cell plus every live non-player block cell in the same
outer board:

```bash
python3 scripts/read_patrick_live_blocks.py
```

If this prints `blocks=0` in a puzzle that visibly has non-player blocks, restart
the game after installing `--live-blocks`; a running game keeps the old DLL in
memory until restart.
The live `block id` is a runtime `DebugID`; match it to asset block information
by cell and interaction type, not by assuming it equals the asset `block_id`.
Static walls are not included in the live block log. Use
`read_patrick_levels.py --level LEVEL_NAME` for walls, buttons, portals, and
other initial terrain.

Render a level from game assets:

```bash
python3 scripts/read_patrick_levels.py --level first_puzzle
```

These tools default to screen coordinates: up is `y - 1`, down is `y + 1`,
left is `x - 1`, and right is `x + 1`. Pass `--coords raw` only when debugging
Unity asset coordinates.

Patrick's Parabox supports chain pushing: pushing can propagate through a
straight line of pushable blocks when every block in the chain has room to move
into the next cell. This is a general movement rule, not a level-specific
solution hint.

List hub portals and their current status:

```bash
python3 scripts/read_patrick_hub.py
```

Statuses are `enterable`, `completed`, or `locked`. The game normally creates
`save_demoN.txt` only after at least one level has been completed, so
`save=not-found` on a fresh run usually means there is no completion data yet.

List which blocks in a level can be entered versus only pushed:

```bash
python3 scripts/read_patrick_blocks.py --level enter
```

Use the `interaction`, `enterable`, and `pushable` fields rather than color.
Yellow-looking blocks can be push-only, and the current player may appear as
another color.
Block positions from this command are initial asset positions; use
`read_patrick_state_log.py` for the current player position and
`read_patrick_live_blocks.py` for current non-player block positions after
pushes.
Each block occupies one cell in its parent board. `inner_size` describes the
inside of a block, not a 5-by-5 outer footprint.

Send one key after manually confirming the current state:

```bash
python3 scripts/patrick_send_keys.py down
```

`patrick_send_keys.py` sends physical key names. Read the log first, then send
the intended key. In this desktop setup, `d` is the most reliable right-move key.

Preview key parsing without sending input:

```bash
python3 scripts/patrick_send_keys.py "down,right" --dry-run
```

If the agent gets stuck inside a puzzle, use the in-game pause/menu path to
return to the previous map layer. Use a longer delay so the menu has time to
open before the selection moves:

```bash
python3 scripts/patrick_send_keys.py "escape,down,enter" --delay 0.35
```

After returning, read the log again before sending any movement key.

## Tool Overview

- `scripts/install_patrick_patch.py`: install, inspect, or restore the game DLL logger patch.
- `scripts/patch_patrick_state_logger.py`: low-level patch implementation.
- `scripts/inspect_dotnet_metadata.py`: .NET metadata and IL inspection.
- `scripts/read_patrick_state_log.py`: parse the newest patched state line from Unity's log.
- `scripts/read_patrick_live_blocks.py`: parse the newest live non-player block cells from Unity's log.
- `scripts/read_patrick_levels.py`: parse and render level layouts from `resources.assets`.
- `scripts/read_patrick_hub.py`: list hub portals as enterable, completed, or locked.
- `scripts/read_patrick_blocks.py`: list level blocks as enterable, push-only, or controlled-player.
- `scripts/patrick_send_keys.py`: activate the game and send key events.
- `scripts/patrick_cgevent_keys.c`: native CoreGraphics key-event helper source.

Solver, route-finder, replay, and screenshot fallback scripts live under
`local_challenge_artifacts/`. That directory is ignored by `.gitignore` and is
not part of the public toolkit.

## Permissions

The toolkit needs local permissions only:

- read/write access to the game's `Assembly-CSharp.dll` while installing or restoring the patch
- read access to Unity's `Player.log`
- read access to the Patrick's Parabox save file when checking progress
- Accessibility permission for automated key input
- Automation permission if macOS asks to let the terminal or agent control `System Events` or Patrick's Parabox

## Changelog

### 2026-04-28

- Added `scripts/install_patrick_patch.py` as the public patch install/status/restore entry point.
- Added `scripts/read_patrick_hub.py` and `scripts/read_patrick_blocks.py` as observation-only tools for hub status and block interaction.
- Added a release-style `README.md` with installation, restore, workflow, permissions, and tool overview.
- Added `AGENTS.MD` with challenge goals and agent operating instructions.
- Split reusable tooling from puzzle-specific scratch artifacts in `.gitignore`.
- Kept `solve_correct_outer.py` ignored because it encodes a one-off strategy for a specific puzzle.
- Moved solver, route-finder, and replay scripts out of the public tool set so fresh agents must reason through the game themselves.
- Moved non-delivered challenge scripts into `local_challenge_artifacts/`.
- Moved screenshot-based position detection into `local_challenge_artifacts/`; the public workflow depends on the log patch instead.
- Switched public state reading and level rendering to screen coordinates by default so up/down match physical movement.
- Added live non-player block position logging and `scripts/read_patrick_live_blocks.py` for current pushed-block cells.
