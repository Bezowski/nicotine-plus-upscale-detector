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

**Producer/consumer.** `download_finished_notification` is the producer: it filters by extension (`_is_audio_file`) and pushes the real path onto a `queue.Queue`. One persistent daemon worker thread (`_worker_loop`, started in `__init__`) is the consumer. This is deliberate — `spectro` is CPU- and RAM-heavy, so files are processed strictly one at a time with a fixed `time.sleep(2)` before each (both to throttle load and to let the file finish flushing to disk). `disable()` sets `stop_event` and joins the worker with a timeout.

**Detection.** `_check_with_spectro` `os.chdir`'s into the file's directory (spectro requires this), runs `spectro check <filename>`, restores cwd in a `finally`, then string/regex-matches stdout:
- `"seems good"` → Passed
- `"has max ... frequency ... Hz"` → Failed, with the cutoff frequency extracted
- `"Don't know what to expect"` → Skipped (format spectro can't judge)
- anything else → returns `None` (logged as unexpected)

`_check_file` wraps this with guard rails: existence check, extension check, and a `max_file_size_mb` cap (default 150) that skips large files because spectro's memory use scales roughly ~100x file size and OOMs otherwise.

**Result shape.** Checks return `{'status': 'Passed'|'Failed'|'Skipped'|'Error', 'reason': str, ...}`. The worker maps status to a symbol (✓/✗/!) and both logs it and, via `_write_to_log_file`, appends to a `spectro_check.log` next to the audio. Log-file naming depends on `music_directory`: files sitting directly in that dir get a per-file log named after the track; files in a subfolder (an album) share one log named after the folder. Skipped files are not written to the log file unless skipped for size.

## Conventions / gotchas

- **Supported formats are exactly `.mp3`, `.flac`, `.wav`** — the set spectro handles. Do not add extensions to `_is_audio_file` without confirming spectro support; the README's format list and this must stay in sync.
- **Windows branch** in `_check_with_spectro`: passes `creationflags=0x08000000` (CREATE_NO_WINDOW) and forces `encoding='utf-8', errors='replace'`, and detects `UnicodeEncodeError` / `charmap` in spectro's stderr as a known Windows limitation. Preserve this when touching subprocess handling.
- **`PLUGININFO`** holds `Version` and the user-facing `Description`; bump/edit it alongside README changes to the same text. It's the only place the version lives.
- No external Python imports beyond the stdlib and `pynicotine` (provided by the Nicotine+ host).
