# Upscale Detector for Nicotine+

Automatically detects upscaled audio files in your Nicotine+ downloads using spectrum analysis. Upscaled files are deceptively labeled with high bitrates (e.g., 320 kbps) but contain lower quality audio that was originally encoded at a lower bitrate (e.g., 128 kbps).

## Features

- 🎵 Monitors completed downloads for audio file upscaling
- 📊 Uses **true-bitrate** spectrum analysis for accurate detection
- 🔍 Supports multiple audio formats: MP3, FLAC, OGG, M4A, AAC, Opus, WMA, ALAC, APE, WAV
- ⚙️ Configurable bitrate tolerance threshold (0-50%)
- 💾 Persistent cache file for results across sessions
- 📝 Clear console logging with status indicators (✓ Passed, ✗ Failed)

## How Upscale Detection Works

### The Problem
An upscaled file is one where someone takes a low-bitrate audio file and re-encodes it at a higher bitrate without improving the audio quality. For example:
- Original: 128 kbps MP3 (real audio quality)
- Re-encoded to: 320 kbps MP3 (metadata says 320 kbps, but audio still sounds like 128 kbps)
- Result: Much larger file size with no quality improvement

### true-bitrate Spectrum Analysis
This plugin uses **true-bitrate** which analyzes the actual audio frequencies present in the file:

- **Real 320 kbps audio** has frequencies across the full spectrum (up to ~20 kHz for human hearing)
- **Upscaled 128 kbps re-encoded to 320 kbps** will have the audio spectrum artificially cut off (~11-13 kHz)
- **true-bitrate detects this frequency cutoff** and calculates the original bitrate

This method is far more accurate than just reading metadata, catching upscales even when the file metadata is faked.

### Detection Examples

**Genuine 320 kbps file:**
```
Declared: 320 kbps
Actual: 320 kbps (20 kHz cutoff)
Result: ✓ PASSED
```

**Upscaled file (128 kbps re-encoded as 320 kbps):**
```
Declared: 320 kbps (metadata says so)
Actual: 128 kbps (14 kHz frequency cutoff detected)
Result: ✗ FAILED
```

## Installation

### 1. Install ffmpeg (Required for metadata reading)

```bash
sudo apt install ffmpeg
```

Verify it works:
```bash
ffprobe -version
```

### 2. Install true-bitrate (Required for spectrum analysis)

#### Step 2a: Install dependencies

```bash
sudo apt install python3-scipy python3-matplotlib
```

#### Step 2b: Clone the true-bitrate repository

```bash
git clone https://github.com/dvorapa/true-bitrate.git
cd true-bitrate
```

#### Step 2c: Fix the path in the wrapper script

The `true-bitrate` script needs to know where `true-bitrate.py` is located. Run:

```bash
sudo sed -i "s|python true-bitrate.py|python $(pwd)/true-bitrate.py|g" true-bitrate
```

Or manually edit the `true-bitrate` file and replace `python true-bitrate.py` with the full path to `true-bitrate.py`

#### Step 2d: Make it available system-wide

```bash
sudo cp true-bitrate /usr/local/bin/true-bitrate
sudo chmod +x /usr/local/bin/true-bitrate
```

#### Step 2e: Test it works

```bash
true-bitrate /path/to/any/audio/file.mp3
```

You should see output like:
```
20 kHz
(20.1065 kHz)
320 kbps
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
4. (Optional) Configure settings in the plugin preferences

## Configuration

In Nicotine+, go to **Preferences → Plugins → Upscale Detector** to configure:

### bitrate_tolerance
Percentage variance allowed between declared and actual bitrate (0-50%, default: 10%)

**Why tolerance is needed:**
- Files can have slight natural variations in actual vs declared bitrate
- VBR (Variable Bitrate) encoding can cause fluctuations
- Some files have padding or metadata that affects measurements

**Recommended values:**
- **5%**: Strict - catches most upscales, may have false positives with VBR files
- **10%**: Balanced (default) - good for most users
- **15-20%**: Lenient - fewer false positives, some upscales might be missed

### auto_check
Enable/disable automatic checking when files complete downloading (default: enabled)

## Usage

### Console Output

When a file finishes downloading, you'll see:

```
Upscale Detector: Checking with true-bitrate: /path/to/file.mp3
Upscale Detector: ✓ Upscale Check: [Passed] file.mp3 - 320kbps (within 10% tolerance)
```

or

```
Upscale Detector: Checking with true-bitrate: /path/to/file.mp3
Upscale Detector: ✗ Upscale Check: [Failed] file.mp3 - Actual 128kbps vs declared 320kbps
```

### Status Indicators

- **✓ [Passed]** - File bitrate matches declaration (genuine file)
- **✗ [Failed]** - Actual bitrate much lower than declared (likely upscaled)
- **- [Skipped]** - Not an audio file (ignored)
- **! [Error]** - Could not analyze file

### Results Cache

Results are saved to: `~/.config/nicotine/upscale_check_cache.json`

View all previous checks:
```bash
cat ~/.config/nicotine/upscale_check_cache.json
```

## Troubleshooting

### "ffprobe not found"
```bash
sudo apt install ffmpeg
```

### "true-bitrate tool not found"
Make sure you:
1. Cloned the repository: `git clone https://github.com/dvorapa/true-bitrate.git`
2. Ran the path fix command
3. Copied to `/usr/local/bin/true-bitrate`
4. Made it executable: `sudo chmod +x /usr/local/bin/true-bitrate`

Test: `true-bitrate /path/to/file.mp3`

### true-bitrate shows DeprecationWarning
This is harmless and doesn't affect functionality. It's a warning from an older version of scipy. It will be fixed in future scipy releases.

### Plugin loads but doesn't check files
1. Make sure `auto_check` is enabled in plugin settings
2. Download a new file to trigger the check
3. Watch the Nicotine+ console for output

### All files show "Error"
1. Check that ffprobe is installed: `ffprobe -version`
2. Check that true-bitrate works: `true-bitrate /path/to/file.mp3`
3. Check file permissions - plugin must be able to read the files

### Too many false positives
Increase the `bitrate_tolerance` setting (try 15-20%)

## Requirements

- **Nicotine+** 3.3.7+
- **Python** 3.8+
- **ffmpeg** (provides ffprobe) - required for metadata reading
- **true-bitrate** - required for spectrum analysis
- **scipy** - required for true-bitrate
- **matplotlib** - required for true-bitrate

## Performance

- Per-file time: 1-5 seconds
- CPU usage: Medium (spectrum analysis)
- Accuracy: High (frequency analysis)

**Tip**: true-bitrate performs FFT (Fast Fourier Transform) analysis on audio, so it's more CPU intensive than simple metadata checking, but the accuracy is worth it!

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

- Spectrum analysis is not 100% foolproof - some edge cases may not be detected
- true-bitrate requires significant CPU for analysis (it's analyzing actual audio data)
- Very short audio files may produce inaccurate results
- Some hand-encoded files with unusual specifications may not be detected
- Plugin must have read access to downloaded files

## Technical Details

### How true-bitrate Works

1. Converts audio to WAV format (uncompressed)
2. Performs FFT (Fast Fourier Transform) on audio samples
3. Analyzes frequency spectrum to find cutoff point
4. Maps frequency cutoff to original bitrate:
   - 11 kHz ≈ 64 kbps
   - 13 kHz ≈ 96 kbps
   - 15 kHz ≈ 128 kbps
   - 17 kHz ≈ 192 kbps
   - 19 kHz ≈ 256 kbps
   - 20+ kHz ≈ 320 kbps (full spectrum)

### Bitrate Tolerance Formula

```
Tolerance = (tolerance_percentage / 100) × declared_bitrate
Difference = declared_bitrate - actual_bitrate

If Difference > Tolerance:
  Status = FAILED (upscaled)
Else:
  Status = PASSED (genuine)
```

Example with 10% tolerance:
```
Declared: 320 kbps
Tolerance: 10% × 320 = 32 kbps
Actual: 300 kbps
Difference: 320 - 300 = 20 kbps

20 < 32? YES → PASSED
```

## Credits

- **Plugin Author**: bez
- **Spectrum Analysis**: [true-bitrate](https://github.com/dvorapa/true-bitrate) by dvorapa
- **Nicotine+**: [Nicotine+ P2P Client](https://nicotine-plus.github.io/nicotine-plus/)
- **Development Assistance**: Claude (Anthropic)

## License

MIT License - See LICENSE file for details

## Contributing

Issues and pull requests are welcome!

## Resources

- [Nicotine+ Documentation](https://nicotine-plus.github.io/nicotine-plus/)
- [true-bitrate GitHub](https://github.com/dvorapa/true-bitrate)
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)
- [Audio Bitrate Information](https://en.wikipedia.org/wiki/Bitrate#Audio)
