# Upscale Detector for Nicotine+

Automatically detects upscaled audio files in your Nicotine+ downloads using spectro frequency analysis. Upscaled files are deceptively labeled with high bitrates (e.g., 320 kbps) but contain lower quality audio that was originally encoded at a lower bitrate (e.g., 128 kbps).

## Features

- 🎵 Monitors completed downloads for audio file upscaling
- 📊 Uses **spectro** frequency analysis for accurate detection
- 🔍 Supports multiple audio formats: MP3, FLAC, OGG, M4A, AAC, Opus, WMA, ALAC, APE, WAV
- 💾 Persistent cache file for results across sessions
- 📝 Clear console logging with status indicators (✓ Passed, ✗ Failed)
- 📈 Displays detected frequency cutoff for suspicious files

## How Upscale Detection Works

### The Problem
An upscaled file is one where someone takes a low-bitrate audio file and re-encodes it at a higher bitrate without improving the audio quality. For example:
- Original: 128 kbps MP3 (real audio quality)
- Re-encoded to: 320 kbps MP3 (metadata says 320 kbps, but audio still sounds like 128 kbps)
- Result: Much larger file size with no quality improvement

### Spectro Frequency Analysis
This plugin uses **spectro** which analyzes the actual audio frequencies present in the file:

- **Real 320 kbps audio** has frequencies across the full spectrum (up to ~20 kHz for human hearing)
- **Upscaled 128 kbps re-encoded to 320 kbps** will have the audio spectrum artificially cut off (~14-16 kHz)
- **Spectro detects this frequency cutoff** and reports if the file "seems good" or has suspicious frequency limits

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
spectro check ~/Music/test.mp3
```

You should see output like:
```
test.mp3 seems good [320 kbps].
```
or
```
test.mp3 is MP3 [320 kbps], but has max frequency about 16780 Hz.
```

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

### auto_check
Enable/disable automatic checking when files complete downloading (default: enabled)

## Usage

### Console Output

When a file finishes downloading, you'll see:

```
Upscale Detector: Checking with spectro: /path/to/file.mp3
Upscale Detector: ✓ Upscale Check: [Passed] file.mp3 - 320 kbps - frequency spectrum looks good
```

or

```
Upscale Detector: Checking with spectro: /path/to/file.mp3
Upscale Detector: ✗ Upscale Check: [Failed] file.mp3 - 320 kbps claimed, but max frequency 16780 Hz - likely upscaled
```

### Status Indicators

- **✓ [Passed]** - File frequency spectrum looks good (genuine file)
- **✗ [Failed]** - Max frequency is lower than expected (likely upscaled)
- **- [Skipped]** - Not an audio file (ignored)
- **! [Error]** - Could not analyze file

### Results Cache

Results are saved to: `~/.config/nicotine/upscale_check_cache.json`

View all previous checks:
```bash
cat ~/.config/nicotine/upscale_check_cache.json
```

## Troubleshooting

### "spectro tool not found"
Make sure you:
1. Installed spectro: `pipx install spectro`
2. Have pipx installed: `sudo apt install pipx`

Test: `spectro check /path/to/file.mp3`

### Plugin loads but doesn't check files
1. Make sure `auto_check` is enabled in plugin settings
2. Download a new file to trigger the check
3. Watch the Nicotine+ console for output

### All files show "Error"
1. Check that spectro is installed: `spectro check ~/Music/test.mp3`
2. Check file permissions - plugin must be able to read the files
3. Ensure audio files aren't corrupted

## Requirements

- **Nicotine+** 3.3.7+
- **Python** 3.8+
- **ffmpeg** - for audio file reading
- **spectro** - for frequency analysis

## Performance

- Per-file time: 2-5 seconds
- CPU usage: Medium (frequency analysis)
- Accuracy: High (frequency-based detection)

Spectro performs FFT (Fast Fourier Transform) analysis on audio, analyzing the actual frequency content to detect upscaling.

## Supported Audio Formats

- MP3 (.mp3)
- FLAC (.flac)
- OGG Vorbis (.ogg)
- M4A (.m4a)
- AAC (.aac)
- Opus (.opus)
- WMA (.wma)
- ALAC (.alac)
- Monkey's Audio (.ape)
- WAV (.wav)

## Limitations

- Spectro's accuracy depends on audio content - some files may have natural frequency limitations
- Very short audio files may produce inaccurate results
- Plugin must have read access to downloaded files
- Detection is based on frequency analysis and may have edge cases

## Technical Details

### How Spectro Works

1. Analyzes the audio file's frequency content
2. Determines the maximum frequency present in the audio
3. Compares against expected frequency range for claimed bitrate:
   - 64 kbps: ~11 kHz
   - 96 kbps: ~13 kHz
   - 128 kbps: ~15 kHz
   - 192 kbps: ~17 kHz
   - 256 kbps: ~19 kHz
   - 320 kbps: ~20 kHz (full spectrum)

4. Reports "seems good" if frequencies match the claimed bitrate
5. Reports suspicious max frequency if frequencies are cut off prematurely

## Credits

- **Plugin Author**: bez
- **Frequency Analysis**: [spectro](https://github.com/nschloe/spectro)
- **Nicotine+**: [Nicotine+ P2P Client](https://nicotine-plus.github.io/nicotine-plus/)
- **Development Assistance**: Claude (Anthropic)

## License

MIT License - See LICENSE file for details

## Contributing

Issues and pull requests are welcome!

## Resources

- [Nicotine+ Documentation](https://nicotine-plus.github.io/nicotine-plus/)
- [spectro GitHub](https://github.com/nschloe/spectro)
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)
- [Audio Bitrate Information](https://en.wikipedia.org/wiki/Bitrate#Audio)
