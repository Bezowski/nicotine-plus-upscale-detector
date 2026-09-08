# Upscale Detector for Nicotine+

Automatically detects upscaled audio files as they download in Nicotine+ using spectrum frequency analysis. Upscaled files are deceptively labeled with high bitrates (e.g., 320 kbps) but contain lower quality audio that was originally encoded at a lower bitrate (e.g., 128 kbps).

## Features

* 🎵 Monitors completed downloads for audio file upscaling
* 📊 Uses **[spectro](https://github.com/nschloe/spectro)** frequency analysis for accurate detection
* 🔍 Supports audio formats: MP3, FLAC, WAV (other formats not supported by spectro)
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

### Linux

#### 1. Install ffmpeg (For audio reading)

```bash
sudo apt install ffmpeg
```

#### 2. Install spectro (Required)

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

#### 3. Install the Plugin

```bash
# Copy the plugin to Nicotine+ plugins directory
cp -r upscale-detector ~/.local/share/nicotine/plugins/

# Or if using a different location:
cp -r upscale-detector /path/to/your/nicotine/plugins/
```

#### 4. Enable the Plugin

1. Start Nicotine+
2. Go to **Preferences → Plugins**
3. Click the checkbox next to **Upscale Detector** to enable it

### Windows

#### 1. Install FFmpeg

```powershell
# Using winget (Windows Package Manager)
winget install ffmpeg

# Restart PowerShell after installation
```

Verify it works:

```powershell
ffmpeg -version
```

#### 2. Install Python (if not already installed)

```powershell
winget install Python.Python.3.12

# Restart PowerShell after installation
```

#### 3. Install pipx and spectro

```powershell
# Install pipx
pip install pipx

# Add pipx to PATH permanently
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";$env:USERPROFILE\.local\bin", "User")

# Restart PowerShell

# Install spectro
pipx install spectro

# Verify it works
spectro --version
```

Test spectro on a music file:

```powershell
cd "C:\Users\YourUsername\Music"
spectro check "song.mp3"
```

#### 4. Install the Plugin

**Option 1: Download from GitHub**
1. Download the latest release from: https://github.com/Bezowski/nicotine-plus-upscale-detector/releases
2. Extract the ZIP file
3. Copy the `upscale-detector` folder to: `C:\Users\YourUsername\AppData\Roaming\nicotine\plugins\`

**Option 2: Use PowerShell**
```powershell
# Download and extract
cd $env:USERPROFILE\Downloads
Invoke-WebRequest -Uri "https://github.com/Bezowski/nicotine-plus-upscale-detector/archive/refs/heads/main.zip" -OutFile "upscale-detector.zip"
Expand-Archive -Path "upscale-detector.zip" -DestinationPath "."

# Copy to plugins directory
Copy-Item -Path ".\nicotine-plus-upscale-detector-main\upscale-detector" -Destination "$env:APPDATA\nicotine\plugins\" -Recurse
```

#### 5. Enable the Plugin

1. Start (or restart) Nicotine+
2. Go to **Preferences → Plugins**
3. Check the box next to **Upscale Detector** to enable it

## Configuration

In Nicotine+, go to **Preferences → Plugins → Upscale Detector** to configure:

### Enable Logging

Enable/disable logging to file (default: enabled)

When enabled, creates log files (`spectro_check.log`) alongside audio files or in album folders.

When disabled, results only appear in the console.

### Music Directory

Path to your downloads directory (default: `~/Music`)

This setting is used to distinguish between:

* Individual files downloaded to your root music directory → creates log file with filename
* Album folders within your music directory → creates log file with folder name

Set this to match your Nicotine+ finished downloads folder. For example:

* `~/Music`
* `~/Downloads/Music`
* `/mnt/media/music`

### Maximum File Size

Maximum file size in MB to check (default: 150)

Files larger than this limit will be skipped to prevent system freezes and out-of-memory errors. Large audio files (200+ MB) can cause spectro to consume excessive RAM (17+ GB for a 261 MB file), which can freeze systems or trigger the OOM killer.

* Set to `150` (recommended for most systems with 16 GB RAM or less)
* Set to `100` for systems with 8 GB RAM or less
* Set to `0` to disable the limit (not recommended - may cause system freezes)

Most music files are well under this limit:
* Typical 320 kbps MP3 track (4 minutes): ~10 MB
* Album (10 tracks): ~100 MB
* Large DJ mixes and live sets may exceed this limit

### Check Delay (seconds)

Seconds to wait before analysing each file (default: 2)

The delay lets the download finish flushing to disk and throttles load, since
spectro is CPU- and RAM-intensive. Raise it if your system stays sluggish while
checks run; set to `0` for no delay.

### Spectro Timeout (seconds)

Give up on a single spectro analysis after this many seconds (default: 60)

Raise it if large files near the size limit are being reported as errors because
the analysis didn't finish in time.

### Notify on Failure

Show a Nicotine+ notification when a likely upscale is found (default: enabled)

The console/log line is always written regardless; this adds a harder-to-miss
popup. Whether a desktop notification actually appears depends on your Nicotine+
notification settings and version.

### Batch Summary

Log a one-line per-folder summary once a batch of downloads finishes (default: enabled)

After an album's files have all been checked, a line like
`Summary [Album Name]: 9 passed, 1 failed - likely upscaled: 03 Track.mp3` is
logged (and appended to the album's log file). Folders with only one checked
file are not summarised.

## Usage

### Automatic Checking

Files are automatically checked when downloads complete. Results are logged to the console and optionally saved to log files.

### Log Files

When logging is enabled, the plugin creates log files with check results:

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

Log files are created in the same directory as the audio files. Each result line is
prefixed with a timestamp, so re-downloading a file or album leaves an
appended history rather than an ambiguous mix of old and new results:

```
[2026-02-14 21:03:11] ✓ [Passed] 01 Track One.mp3 - 320 kbps - frequency spectrum looks good
[2026-02-14 21:03:14] ✓ [Passed] 02 Track Two.mp3 - 320 kbps - frequency spectrum looks good
[2026-02-14 21:03:18] ✗ [Failed] 03 Track Three.mp3 - 320 kbps claimed, but max frequency 16780 Hz - likely upscaled
```

### Console Output

When a file finishes downloading, you'll see:

```
Upscale Detector: ✓ [Passed] file.mp3 - 320 kbps - frequency spectrum looks good
```

or, for a likely upscale, an extra prominent line (and a Nicotine+ notification
unless disabled):

```
Upscale Detector: ✗ [Failed] file.mp3 - 320 kbps claimed, but max frequency 16780 Hz - likely upscaled
Upscale Detector: ⚠ UPSCALE DETECTED: file.mp3 - 320 kbps claimed, but max frequency 16780 Hz - likely upscaled
```

Once a folder's downloads finish, a summary line follows (see **Batch Summary**):

```
Upscale Detector: Summary [Album Name]: 9 passed, 1 failed - likely upscaled: 03 Track Three.mp3
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

The plugin waits a configurable delay (default 2 seconds) before each file check to prevent system overload. If you still experience sluggishness:

1. Check system resources with `htop` during file checks
2. Consider checking large files manually after downloads complete
3. Raise **Check Delay (seconds)** in the plugin settings

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

* **Upscale Detector** v1.1.0
* **Nicotine+** 3.3.7+
* **Python** 3.8+
* **ffmpeg** - for audio file reading
* **spectro** - for frequency analysis

**Supported Platforms:**
- Linux (tested)
- Windows 11 (tested)

## Performance

* Per-file time: 2-5 seconds (varies with file size and system)
* CPU usage: Medium (frequency analysis is CPU-intensive)
* Memory usage: Low (single-threaded queue processing)
* Accuracy: High (frequency-based detection)

Spectro performs FFT (Fast Fourier Transform) analysis on audio, analyzing the actual frequency content to detect upscaling. The plugin processes files one at a time to prevent system overload.

## Supported Audio Formats

Spectro only supports a limited number of formats:

* MP3 (.mp3) ✓
* FLAC (.flac) ✓
* WAV (.wav) ✓

### Unsupported Formats (will be skipped)

* AAC (.aac) ✗
* M4A (.m4a) ✗
* OGG Vorbis (.ogg) ✗
* Opus (.opus) ✗
* WMA (.wma) ✗
* ALAC (.alac) ✗
* Monkey's Audio (.ape) ✗

These formats will be ignored by the plugin and won't be checked for upscaling.

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