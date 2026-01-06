# Upscale Detector for Nicotine+

Automatically detects upscaled audio files as they download in Nicotine+ using spectrum frequency analysis. Upscaled files are deceptively labeled with high bitrates (e.g., 320 kbps) but contain lower quality audio that was originally encoded at a lower bitrate (e.g., 128 kbps).

## Features

* 🎵 Monitors completed downloads for audio file upscaling
* 📊 Uses **[spectro](https://github.com/nschloe/spectro)** frequency analysis for accurate detection
* 🔍 Supports multiple audio formats: MP3, FLAC, M4A, AAC, Opus, WMA, ALAC, APE, WAV (OGG not supported by spectro)
* 📝 Clear console logging with status indicators (✓ Passed, ✗ Failed)
* 📈 Displays detected frequency cutoff for suspicious files
* ⚡ Efficient single-threaded queue processing to prevent system overload

## How Upscale Detection Works

### The Problem

An upscaled file is one where someone takes a low-bitrate audio file and re-encodes it at a higher bitrate without improving the audio quality. For example:

* Original: 128 kbps MP3 (real audio quality)
* Re-encoded to: 320 kbps MP3 (metadata says 320 kbps, but audio still sounds like 128 kbps)
* Result: Much larger file size with no quality improvement

### Spectro Frequency Analysis

This plugin uses **spectro** which analyzes the actual audio frequencies present in the file:

* **Real 320 kbps audio** has frequencies across the full spectrum (up to ~20 kHz for human hearing)
* **Upscaled 128 kbps re-encoded to 320 kbps** will have the audio spectrum artificially cut off (~14-16 kHz)
* **Spectro detects this frequency cutoff** and reports if the file "seems good" or has suspicious frequency limits

This method is far more accurate than just reading metadata, catching upscales even when the file metadata is faked.

### Detection Examples

**Genuine 320 kbps file:**

```
02 Derelicts of Dialect.mp3 seems good [320 kbps].
Result: ✓ PASSED
```

**Upscaled file (128 kbps re-encoded as 320 kbps):**

```
03 Ace in the Hole.mp3 is MP3 [320 kbps], but has max frequency about 16780 Hz.
Result: ✗ FAILED - max frequency 16780 Hz detected
```

## Installation

### 1. Install ffmpeg (For audio reading)

```bash
sudo apt install ffmpeg
```

### 2. Install spectro (Required)

```bash
pipx install spectro
```

Or if you don't have pipx installed:

```bash
sudo apt install pipx
pipx install spectro
```

Verify it works:

```bash
cd ~/Music
spectro check test.mp3
```

You should see output like:

```
test.mp3 seems good [320 kbps].
```

or

```
test.mp3 is MP3 [320 kbps], but has max frequency about 16780 Hz.
```

**Note:** spectro must be run from the same directory as the audio file when checking individual files.

### 3. Install the Plugin

```bash
# Copy the plugin to Nicotine+ plugins directory
cp -r upscale-detector ~/.local/share/nicotine/plugins/

# Or if using a different location:
cp -r upscale-detector /path/to/your/nicotine/plugins/
```

### 4. Enable the Plugin

1. Start Nicotine+
2. Go to **Preferences → Plugins**
3. Click the checkbox next to **Upscale Detector** to enable it

## Configuration

In Nicotine+, go to **Preferences → Plugins → Upscale Detector** to configure:

### enable_logging

Enable/disable logging to file (default: enabled)

When enabled, creates log files (`spectro_check.log`) alongside audio files or in album folders.

When disabled, results only appear in the console.

### music_directory

Path to your music directory (default: `~/Music`)

This setting is used to distinguish between:

* Individual files downloaded to your root music directory → creates log file with filename
* Album folders within your music directory → creates log file with folder name

Set this to match your Nicotine+ downloads folder. For example:

* `~/Music`
* `~/Downloads/Music`
* `/mnt/media/music`

### max_file_size_mb

Maximum file size in MB to check (default: 150)

Files larger than this limit will be skipped to prevent system freezes and out-of-memory errors. Large audio files (200+ MB) can cause spectro to consume excessive RAM (17+ GB for a 261 MB file), which can freeze systems or trigger the OOM killer.

* Set to `150` (recommended for most systems with 16 GB RAM or less)
* Set to `100` for systems with 8 GB RAM or less
* Set to `0` to disable the limit (not recommended - may cause system freezes)

Most music files are well under this limit:
* Typical 320 kbps MP3 track (4 minutes): ~10 MB
* Album (10 tracks): ~100 MB
* Large DJ mixes and live sets may exceed this limit

## Usage

### Automatic Checking

Files are automatically checked when downloads complete. Results are logged to the console and optionally saved to log files.

### Log Files

When `enable_logging` is enabled, the plugin creates log files with check results:

**For album/folder downloads:**

```
~/Music/2004 - The Grey Album (with Danger Mouse)/
├── 01 - Track One.mp3
├── 02 - Track Two.mp3
└── 2004 - The Grey Album (with Danger Mouse) - spectro_check.log
```

**For individual file downloads:**

```
~/Music/
├── Eric Sneo Live @ Kinki Palace (03-10-07).mp3
└── Eric Sneo Live @ Kinki Palace (03-10-07) - spectro_check.log
```

Log files are created in the same directory as the audio files and contain check results in this format:

```
✓ [Passed] 01 Track One.mp3 - 320 kbps - frequency spectrum looks good
✓ [Passed] 02 Track Two.mp3 - 320 kbps - frequency spectrum looks good
✗ [Failed] 03 Track Three.mp3 - 320 kbps claimed, but max frequency 16780 Hz - likely upscaled
```

### Console Output

When a file finishes downloading, you'll see:

```
Upscale Detector: ✓ [Passed] file.mp3 - 320 kbps - frequency spectrum looks good
```

or

```
Upscale Detector: ✗ [Failed] file.mp3 - 320 kbps claimed, but max frequency 16780 Hz - likely upscaled
```

### Status Indicators

* **✓ [Passed]** - File frequency spectrum looks good (genuine file)
* **✗ [Failed]** - Max frequency is lower than expected (likely upscaled)
* **- [Skipped]** - File too large or not an audio file
* **! [Error]** - Could not analyze file

## Troubleshooting

### "spectro tool not found"

Make sure you:

1. Installed spectro: `pipx install spectro`
2. Have pipx installed: `sudo apt install pipx`

Test: `spectro check /path/to/file.mp3`

### Plugin loads but doesn't check files

1. Download a new file to trigger the check
2. Watch the Nicotine+ console for output
3. Check that you see "Worker thread started" when plugin loads

### All files show "Error"

1. Check that spectro is installed: `spectro check ~/Music/test.mp3`
2. Check file permissions - plugin must be able to read the files
3. Ensure audio files aren't corrupted
4. Check the console for spectro error messages

### System becomes sluggish during checks

The plugin includes a 2-second delay between file checks to prevent system overload. If you still experience sluggishness:

1. Check system resources with `htop` during file checks
2. Consider checking large files manually after downloads complete
3. You can modify the delay in the code: change `time.sleep(2)` to a higher value in `__init__.py`

### Large files cause system to freeze or get "Killed"

Spectro can consume excessive memory on very large files (17+ GB RAM for a 261 MB file). The plugin has a default 150 MB file size limit to prevent this:

1. Files over 150 MB are automatically skipped with a log message
2. Adjust `max_file_size_mb` in plugin settings if needed
3. You can check large files manually, but be aware they may trigger the OOM killer
4. To check if OOM killer was triggered: `sudo dmesg | grep -i "out of memory"`

For reference on RAM usage vs file size:
* 100 MB file: ~10 GB RAM needed
* 150 MB file: ~13 GB RAM needed (safe for 16 GB systems)
* 200+ MB files: 15+ GB RAM needed (likely to cause OOM on most systems)

## Requirements

* **Nicotine+** 3.3.7+
* **Python** 3.8+
* **ffmpeg** - for audio file reading
* **spectro** - for frequency analysis

## Performance

* Per-file time: 2-5 seconds (varies with file size and system)
* CPU usage: Medium (frequency analysis is CPU-intensive)
* Memory usage: Low (single-threaded queue processing)
* Accuracy: High (frequency-based detection)

Spectro performs FFT (Fast Fourier Transform) analysis on audio, analyzing the actual frequency content to detect upscaling. The plugin processes files one at a time to prevent system overload.

## Supported Audio Formats

* MP3 (.mp3) ✓
* FLAC (.flac) ✓
* M4A (.m4a) ✓
* AAC (.aac) ✓
* Opus (.opus) ✓
* WMA (.wma) ✓
* ALAC (.alac) ✓
* Monkey's Audio (.ape) ✓
* WAV (.wav) ✓
* OGG Vorbis (.ogg) ✗ (not supported by spectro - will be skipped)

## Limitations

* Spectro's accuracy depends on audio content - some files may have natural frequency limitations
* Very short audio files may produce inaccurate results
* Plugin must have read access to downloaded files
* Detection is based on frequency analysis and may have edge cases
* Large files (100+ MB) take longer to analyze

## Technical Details

### How Spectro Works

1. Analyzes the audio file's frequency content using FFT
2. Determines the maximum frequency present in the audio
3. Compares against expected frequency range for claimed bitrate:
   * 64 kbps: ~11 kHz
   * 96 kbps: ~13 kHz
   * 128 kbps: ~15 kHz
   * 192 kbps: ~17 kHz
   * 256 kbps: ~19 kHz
   * 320 kbps: ~20 kHz (full spectrum)
4. Reports "seems good" if frequencies match the claimed bitrate
5. Reports suspicious max frequency if frequencies are cut off prematurely

### Queue Processing

The plugin uses a thread-safe queue to process files sequentially:

* One persistent worker thread handles all checks
* Files are queued as downloads complete
* Configurable delay between checks prevents system overload
* Thread-safe implementation prevents race conditions

## Credits

* **Plugin Author**: bez
* **Frequency Analysis**: [spectro](https://github.com/nschloe/spectro)
* **Nicotine+**: [Nicotine+ P2P Client](https://nicotine-plus.github.io/nicotine-plus/)
* **Development Assistance**: Claude (Anthropic)

## License

MIT License - See LICENSE file for details

## Contributing

Issues and pull requests are welcome!

## Resources

* [Nicotine+ Documentation](https://nicotine-plus.github.io/nicotine-plus/)
* [spectro GitHub](https://github.com/nschloe/spectro)
* [FFmpeg Documentation](https://ffmpeg.org/documentation.html)
* [Audio Bitrate Information](https://en.wikipedia.org/wiki/Bitrate#Audio)
