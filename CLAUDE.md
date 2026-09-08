# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-file plugin for [Nicotine+](https://nicotine-plus.github.io/nicotine-plus/) (a Soulseek client). It watches completed downloads and runs the external `spectro` tool to flag audio files whose real frequency content is lower than their claimed bitrate (i.e. upscaled/transcoded fakes).

All plugin code lives in `upscale-detector/__init__.py`. `upscale-detector/PLUGININFO` is the Nicotine+ manifest.

## No build / test / lint tooling

There is no package manifest, test suite, CI, or linter config. "Testing" is manual:

1. Copy the `upscale-detector/` folder into the Nicotine+ plugins dir
   (`~/.local/share/nicotine/plugins/` on Linux, `%APPDATA%\nicotine\plugins\` on Windows).
2. Restart Nicotine+, enable **Upscale Detector** under **Preferences → Plugins**.
3. Trigger a download (or re-download) of an `.mp3` / `.flac` / `.wav` and watch the Nicotine+ log console. `Worker thread started` on load confirms the plugin is live.

To exercise the detection logic without Nicotine+, run the underlying tool directly — it must be invoked from the file's own directory:

```bash
cd /path/to/music && spectro check "song.mp3"
```

Runtime deps the plugin shells out to: `spectro` (`pipx install spectro`) and `ffmpeg`.

## Architecture

**Plugin contract.** `Plugin(BasePlugin)` from `pynicotine.pluginsystem`. Nicotine+ instantiates it, reads `self.settings` / `self.metasettings` (defined in `__init__`) to render the preferences UI, calls `download_finished_notification(user, virtual_path, real_path)` per completed file, and calls `disable()` on unload. `self.log(...)` writes to the Nicotine+ console.

**Producer/consumer.** `download_finished_notification` is the producer: it filters by extension (`_is_audio_file`) and pushes the real path onto a `queue.Queue`. One persistent daemon worker thread (`_worker_loop`, started in `__init__`) is the consumer. This is deliberate — `spectro` is CPU- and RAM-heavy, so files are processed strictly one at a time with a `CHECK_DELAY_SECONDS` sleep (module constant, default 2) before each (both to throttle load and to let the file finish flushing to disk). `disable()` sets `stop_event`, kills any in-flight `spectro` via the tracked `self._current_proc`, and joins the worker with a timeout.

**Batch summary.** `_report_result` accumulates per-directory tallies in `self._pending`. When the queue drains (the `queue.Empty` branch of `_worker_loop`, and again in `disable()`), `_flush_summaries` emits one `Summary [folder]: N passed, M failed …` line per directory that saw 2+ files, appends it to that album's log, and clears `_pending`. Idle `queue.Empty` ticks re-call it cheaply (empty dict → early return).

**Detection.** `_check_with_spectro` runs `spectro check <filename>` with `cwd=file_dir` (spectro must run from the file's own directory; never `os.chdir` — this is the host Nicotine+ process). It uses `subprocess.Popen` + `communicate(timeout=SPECTRO_TIMEOUT_SECONDS)` (module constant, default 60) so the child is reachable for `disable()` to kill. Then it string/regex-matches stdout:
- `"seems good"` → Passed
- `"has max ... frequency ... Hz"` → Failed, with the cutoff frequency extracted
- `"Don't know what to expect"` → Skipped (format spectro can't judge)
- anything else → `Error` carrying the raw output text (so an unparseable result still gets recorded, not dropped)

`_check_file` wraps this with guard rails: existence check, extension check, and a `max_file_size_mb` cap (default 150) that skips large files because spectro's memory use scales roughly ~100x file size and OOMs otherwise.

**Result shape.** Checks return `{'status': 'Passed'|'Failed'|'Skipped'|'Error', 'reason': str, ...}`. `_report_result` maps status to a glyph via `_SYMBOLS` (`✓`/`✗`/`-`, default `!` for Error), logs it, and appends to a `spectro_check.log` next to the audio. `_write_to_log_file` resolves the path (per-file log named after the track for files directly in `music_directory`; one shared log named after the folder for files in a subfolder) and delegates to `_append_log`, which prepends a timestamp and is the single gate on `enable_logging`. Skipped files are not written to the log unless skipped for size. A `Failed` result also emits a prominent `⚠ UPSCALE DETECTED` line and calls `_notify` (best-effort `self.core.notifications.new_text_notification`, fully guarded — the API varies by Nicotine+ version, so the log line is the real record).

## Conventions / gotchas

- **Supported formats are exactly `.mp3`, `.flac`, `.wav`** — the set spectro handles. Do not add extensions to `_is_audio_file` without confirming spectro support; the README's format list and this must stay in sync.
- **Windows branch** in `_check_with_spectro`: passes `creationflags=0x08000000` (CREATE_NO_WINDOW) and forces `encoding='utf-8', errors='replace'`, and detects `UnicodeEncodeError` / `charmap` in spectro's stderr as a known Windows limitation. Preserve this when touching subprocess handling. `_append_log` also opens the log file `encoding='utf-8'` for the same reason (glyphs + non-Latin track names).
- **`PLUGININFO`** holds `Version` and the user-facing `Description`; bump/edit it alongside README changes to the same text. It's the only place the version lives.
- No external Python imports beyond the stdlib and `pynicotine` (provided by the Nicotine+ host).
