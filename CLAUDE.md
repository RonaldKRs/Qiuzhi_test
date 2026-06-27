# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-file desktop Pomodoro timer (`pomodoro.py`) built with Python's standard-library tkinter. No third-party dependencies, no build step, no test suite. `README.md`, `test.txt`, and `Qiuzhi_test/` are scratch/test artifacts (the latter two are gitignored) — not part of the app.

## Running

Windows only — the app uses `winsound` for the end-of-timer beep, which has no cross-platform fallback.

```
C:/Users/Reginald/AppData/Local/Python/pythoncore-3.14-64/python.exe pomodoro.py
```

Use the full interpreter path: a bare `python` on this machine resolves to the Windows Store stub, not a real interpreter. Paths passed to tools that run via Git Bash (`sh -c`) must use forward slashes — backslashes get eaten as escape characters.

## Architecture (`pomodoro.py`)

One class, `PomodoroApp(tk.Tk)`. The design centers on a deliberate **create-once / update-in-place** rendering strategy — understand this before editing the UI:

- **Canvas items are created exactly once** in `_build_ui()` (background ring, progress arc, time text, mode label, tip text) and stored as `self._*_item`. Everything afterward mutates them with `itemconfig()`; nothing is ever deleted and recreated. The same applies to the progress dots and tab buttons. Fonts are pre-built as `tkfont.Font` objects so tkinter doesn't re-parse font tuples on every call.
- **Two refresh tiers, kept separate on purpose:**
  - `_update_display()` is the per-second hot path. It only touches the two things that change every tick: the countdown text and the arc's `extent`. Keep it minimal.
  - `_apply_mode_style()` runs *only* on a mode switch. It recolors the arc, mode label, start button, tabs, and dots. Do not call it per tick.

- **Mode state machine.** Three modes (`work`, `short_break`, `long_break`) drive everything through two lookup dicts, `MODE_MINUTES` and `MODE_COLORS`. Flow: a completed work session calls `_advance_mode()`, which decides the next mode (long break every `POMODOROS_BEFORE_LONG_BREAK` pomodoros, else short break, and breaks always return to work). All transitions funnel through the single entry point `_set_mode()`, which resets the time and calls `_apply_mode_style()`.

- **Timer control.** `_tick()` self-schedules with `after(1000, ...)` and stores the handle in `self._after_id`. `_stop()` is the shared teardown (cancels the pending `after`, resets the button) used by reset / skip / timer-end; `_pause()` layers "继续" button text on top of it. Always cancel `_after_id` when stopping to avoid orphaned callbacks.

- **Sound** runs in a daemon thread (`_beep` via `winsound.Beep`) so the blocking beep never freezes the tk event loop.

## Conventions

- Colors and layout constants live in the top-of-file config block (warm light theme: terracotta / sage / slate on cream). Change appearance there, not inline.
- UI strings are Chinese (Simplified); keep new user-facing text consistent.
