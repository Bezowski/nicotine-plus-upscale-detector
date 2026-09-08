"""
Nicotine+ Upscale Detector Plugin
Detects upscaled audio files after download using spectro frequency analysis
"""

import os
import subprocess
import threading
import queue
import re
import time
from datetime import datetime
from pathlib import Path
from pynicotine.pluginsystem import BasePlugin

# Tunables that rarely need changing (see README troubleshooting). Kept here
# rather than as plugin settings to avoid cluttering the preferences panel.
CHECK_DELAY_SECONDS = 2       # pause before each check: lets the file settle, throttles load
SPECTRO_TIMEOUT_SECONDS = 60  # give up on a single spectro analysis after this long
SUMMARY_QUIET_SECONDS = 60    # emit a folder's batch summary once no new file has arrived for this long


class Plugin(BasePlugin):
    """
    Monitors completed downloads and checks if audio files are upscaled using spectro
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.settings = {
            'enable_logging': True,
            'music_directory': str(Path.home() / 'Music'),
            'max_file_size_mb': 150,
            'notify_on_failure': True,
            'batch_summary': True,
        }

        self.metasettings = {
            'enable_logging': {
                'description': 'Enable logging to file (spectro_check.log)',
                'type': 'bool'
            },
            'music_directory': {
                'description': 'Path to your music directory (for individual file logging)',
                'type': 'str'
            },
            'max_file_size_mb': {
                'description': 'Skip files larger than this size in MB (0 = no limit)',
                'type': 'int',
                'minimum': 0
            },
            'notify_on_failure': {
                'description': 'Show a Nicotine+ notification when a likely upscale is found',
                'type': 'bool'
            },
            'batch_summary': {
                'description': 'Log a per-folder summary once a batch of downloads finishes',
                'type': 'bool'
            },
        }

        self.file_queue = queue.Queue()
        self.worker_thread = None
        self.stop_event = threading.Event()
        self._current_proc = None
        # Per-directory result tallies awaiting a batch summary, keyed by dir path
        self._pending = {}
        
        self.log("Upscale Detector initialized")
        
        # Start the persistent worker thread
        self._start_worker()
    
    def _start_worker(self):
        """Start the persistent worker thread"""
        if self.worker_thread is None or not self.worker_thread.is_alive():
            self.stop_event.clear()
            self.worker_thread = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name="UpscaleDetectorWorker"
            )
            self.worker_thread.start()
            self.log("Worker thread started")
    
    def _worker_loop(self):
        """Persistent worker that continuously processes the queue"""
        while not self.stop_event.is_set():
            try:
                # Wait for a file with timeout so we can check stop_event
                filepath = self.file_queue.get(timeout=1)
            except queue.Empty:
                # Queue drained for now - flush any pending batch summaries
                self._flush_summaries()
                continue

            try:
                # Wait before checking, both to let the file finish flushing to
                # disk and to throttle load (spectro is CPU/RAM heavy)
                if CHECK_DELAY_SECONDS > 0:
                    time.sleep(CHECK_DELAY_SECONDS)

                # Verify file still exists and is readable
                if not os.path.exists(filepath):
                    self.log(f"File disappeared before check: {os.path.basename(filepath)}")
                elif not os.access(filepath, os.R_OK):
                    self.log(f"File not readable: {os.path.basename(filepath)}")
                else:
                    result = self._check_file(filepath)
                    if result:
                        self._report_result(filepath, result)

            except Exception as e:
                self.log(f"Worker thread error: {e}")
                # Continue processing other files even if one fails
            finally:
                # Mark task as done exactly once per dequeued item
                self.file_queue.task_done()

    # Glyph per status - matches the table in the README
    _SYMBOLS = {'Passed': '✓', 'Failed': '✗', 'Skipped': '-'}

    def _report_result(self, filepath, result):
        """Log one check result and fold it into the pending batch summary"""
        status = result.get('status', 'Unknown')
        reason = result.get('reason', '')
        filename = os.path.basename(filepath)
        file_dir = os.path.dirname(filepath)

        parent_dir = os.path.basename(file_dir) if file_dir else ''
        display_path = f"{parent_dir}/{filename}" if parent_dir else filename
        symbol = self._SYMBOLS.get(status, '!')

        # A failed check gets a "⚠" prefix so it stands out in a busy log,
        # rather than a separate duplicate line
        prefix = '⚠ ' if status == 'Failed' else ''
        self.log(f"{prefix}{symbol} [{status}] {display_path} - {reason}")

        # Write to log file (skip "not an audio file" skips, keep size skips)
        if status != 'Skipped' or 'too large' in reason:
            self._write_to_log_file(filepath, f"{prefix}{symbol} [{status}] {filename} - {reason}")

        if status == 'Failed':
            self._notify(f"Likely upscaled: {display_path}\n{reason}")

        # Accumulate for the per-folder batch summary
        tally = self._pending.setdefault(
            file_dir,
            {'Passed': 0, 'Failed': 0, 'Skipped': 0, 'Error': 0, 'failed': [], 'last_seen': 0.0},
        )
        tally[status] = tally.get(status, 0) + 1
        tally['last_seen'] = time.time()
        if status == 'Failed':
            tally['failed'].append(filename)

    def _flush_summaries(self, force=False):
        """Emit a per-folder summary once that folder has gone quiet.

        Runs on every idle tick. A folder is only summarised (and dropped) once
        no new file has arrived for SUMMARY_QUIET_SECONDS, so an album that
        downloads track by track still accumulates into a single summary rather
        than being discarded one file at a time. `force` flushes everything
        regardless (used on disable).
        """
        if not self._pending:
            return

        now = time.time()
        enabled = self.settings.get('batch_summary', True)
        music_dir = os.path.expanduser(self.settings['music_directory'])

        for file_dir in list(self._pending):
            tally = self._pending[file_dir]
            if not force and now - tally['last_seen'] < SUMMARY_QUIET_SECONDS:
                continue  # folder still active - wait for it to settle

            del self._pending[file_dir]

            total = tally['Passed'] + tally['Failed'] + tally['Skipped'] + tally['Error']
            if total < 2 or not enabled:
                continue  # single files already have their own result line

            folder = os.path.basename(file_dir) or file_dir
            parts = [f"{tally['Passed']} passed", f"{tally['Failed']} failed"]
            if tally['Skipped']:
                parts.append(f"{tally['Skipped']} skipped")
            if tally['Error']:
                parts.append(f"{tally['Error']} error" + ('s' if tally['Error'] != 1 else ''))

            summary = f"Summary [{folder}]: " + ", ".join(parts)
            if tally['failed']:
                summary += " - likely upscaled: " + ", ".join(tally['failed'])

            self.log(summary)

            # Anchor the summary in an album folder's own log (not the root dir,
            # where each file keeps its own separate log)
            if file_dir != music_dir:
                self._append_log(
                    os.path.join(file_dir, f"{folder} - spectro_check.log"), summary
                )

            if tally['failed']:
                self._notify(
                    f"{folder}: {len(tally['failed'])} likely upscaled\n"
                    + "\n".join(tally['failed'])
                )

    def _notify(self, message):
        """Best-effort Nicotine+ notification; the log line is the real record"""
        if not self.settings.get('notify_on_failure', True):
            return
        core = getattr(self, 'core', None)
        if core is None:
            return
        try:
            core.notifications.new_text_notification(message, title="Upscale Detector")
        except Exception:
            try:
                core.notifications.new_text_notification(message)
            except Exception:
                pass  # notifications API differs by Nicotine+ version - log stands
    
    def download_finished_notification(self, user, virtual_path, real_path):
        """Called when a file download completes"""
        # Always queue audio files for checking
        if self._is_audio_file(real_path):
            self._queue_file_check(real_path)
    
    def _queue_file_check(self, filepath):
        """Add a file to the check queue (thread-safe)"""
        self.file_queue.put(filepath)
    
    def _check_file(self, filepath):
        """
        Check if an audio file is upscaled using spectro
        Returns: {'status': 'Passed'|'Failed'|'Skipped'|'Error', 'reason': str, 'timestamp': float}
        """
        if not os.path.exists(filepath):
            return {'status': 'Error', 'reason': 'File not found', 'timestamp': time.time()}
        
        if not self._is_audio_file(filepath):
            return {'status': 'Skipped', 'reason': 'Not an audio file', 'timestamp': time.time()}
        
        # Check file size limit
        max_size_mb = self.settings.get('max_file_size_mb', 150)
        if max_size_mb > 0:
            file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
            if file_size_mb > max_size_mb:
                return {
                    'status': 'Skipped',
                    'reason': f'File too large ({file_size_mb:.1f} MB > {max_size_mb} MB limit)',
                    'timestamp': time.time()
                }
        
        try:
            result = self._check_with_spectro(filepath)
            
            if result is None:
                return {
                    'status': 'Error',
                    'reason': 'Could not analyze file',
                    'timestamp': time.time()
                }
            
            return result
            
        except Exception as e:
            self.log(f"Error checking {filepath}: {e}")
            return {'status': 'Error', 'reason': str(e), 'timestamp': time.time()}
    
    def _check_with_spectro(self, filepath):
        """Use spectro for frequency analysis of individual files"""
        try:
            # Get directory and filename
            file_dir = os.path.dirname(filepath)
            filename = os.path.basename(filepath)

            # Run spectro from the file's own directory (spectro requires this).
            # Pass it as the subprocess cwd rather than calling os.chdir, so the
            # working directory of the host Nicotine+ process is never mutated.
            cmd = ['spectro', 'check', filename]
            popen_kwargs = {
                'cwd': file_dir or None,
                'stdout': subprocess.PIPE,
                'stderr': subprocess.PIPE,
                'text': True,
            }

            # On Windows, hide the console window and force UTF-8 decoding
            if os.name == 'nt':
                popen_kwargs['creationflags'] = 0x08000000
                popen_kwargs['encoding'] = 'utf-8'
                popen_kwargs['errors'] = 'replace'

            proc = subprocess.Popen(cmd, **popen_kwargs)
            self._current_proc = proc
            try:
                stdout, stderr = proc.communicate(timeout=SPECTRO_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                raise
            finally:
                self._current_proc = None
            returncode = proc.returncode

            if returncode != 0:
                # Log stderr if spectro failed
                error_msg = stderr.strip() if stderr else "Unknown error"
                
                # On Windows, spectro can crash with unicode filenames - detect this
                if 'UnicodeEncodeError' in error_msg or 'charmap' in error_msg:
                    self.log(f"spectro failed for {filename}: Unicode encoding error (Windows limitation)")
                    return {
                        'status': 'Error',
                        'reason': 'Filename contains unsupported characters (Windows)',
                        'timestamp': time.time()
                    }
                
                self.log(f"spectro failed for {filename}: {error_msg}")
                return None
            
            # Parse spectro output - join all lines in case output is wrapped
            output_line = ' '.join(stdout.strip().split())
            
            # Check if spectro doesn't support this format
            if "Don't know what to expect" in output_line or "don't know what to expect" in output_line.lower():
                return {
                    'status': 'Skipped',
                    'reason': 'Format not supported by spectro',
                    'timestamp': time.time()
                }
            
            if 'seems good' in output_line:
                # Extract bitrate or format
                bitrate_match = re.search(r'\[(\d+)\s*kbps\]', output_line)
                format_match = re.search(r'is\s+(WAV|FLAC|MP3)', output_line, re.IGNORECASE)
                
                if bitrate_match:
                    bitrate = bitrate_match.group(1)
                    display = f'{bitrate} kbps'
                elif format_match:
                    format_type = format_match.group(1).upper()
                    display = format_type
                else:
                    # No format in output - infer from filename
                    ext = os.path.splitext(filepath)[1].lower().replace('.', '').upper()
                    if ext in ['FLAC', 'WAV', 'MP3']:
                        display = ext
                    else:
                        display = 'unknown format'
                
                return {
                    'status': 'Passed',
                    'bitrate': display,
                    'reason': f'{display} - frequency spectrum looks good',
                    'timestamp': time.time()
                }
            elif 'has max' in output_line and 'frequency' in output_line:
                # Extract bitrate/format and frequency
                bitrate_match = re.search(r'\[(\d+)\s*kbps\]', output_line)
                format_match = re.search(r'is\s+(WAV|FLAC|MP3)', output_line, re.IGNORECASE)
                freq_match = re.search(r'(?:about\s+)?(\d+)\s*Hz', output_line)
                
                if bitrate_match:
                    display = f'{bitrate_match.group(1)} kbps'
                elif format_match:
                    display = format_match.group(1).upper()
                else:
                    # Infer from filename extension
                    ext = os.path.splitext(filepath)[1].lower().replace('.', '').upper()
                    if ext in ['FLAC', 'WAV', 'MP3']:
                        display = ext
                    else:
                        display = 'unknown format'
                
                frequency = freq_match.group(1) if freq_match else 'unknown'
                
                return {
                    'status': 'Failed',
                    'bitrate': display,
                    'frequency': frequency,
                    'reason': f'{display} claimed, but max frequency {frequency} Hz - likely upscaled',
                    'timestamp': time.time()
                }
            else:
                # Output doesn't match any known spectro verdict - record it as an
                # error carrying the raw text instead of silently dropping the check
                snippet = output_line if len(output_line) <= 200 else output_line[:200] + '...'
                self.log(f"Unexpected spectro output for {filename}: {output_line}")
                return {
                    'status': 'Error',
                    'reason': f'Unrecognized spectro output: {snippet}',
                    'timestamp': time.time()
                }

        except FileNotFoundError:
            self.log("spectro tool not found. Install: pipx install spectro")
            return None
        except subprocess.TimeoutExpired:
            self.log(f"spectro analysis timed out for {os.path.basename(filepath)}")
            return None
        except Exception as e:
            self.log(f"Error with spectro for {os.path.basename(filepath)}: {e}")
            return None
    
    def _is_audio_file(self, filepath):
        """Check if file is an audio file that spectro can analyze"""
        # Only formats spectro actually supports
        audio_extensions = {
            '.mp3', '.flac', '.wav'
        }
        return os.path.splitext(filepath)[1].lower() in audio_extensions
    
    def _write_to_log_file(self, filepath, log_message):
        """Write a check result to the log for the given audio file.

        Files in the root music directory get one log per file (named after the
        file); files in a subdirectory (album folder) share one log named after
        the folder.
        """
        file_dir = os.path.dirname(filepath)
        filename = os.path.basename(filepath)
        music_dir = os.path.expanduser(self.settings['music_directory'])

        if file_dir == music_dir:
            base = os.path.splitext(filename)[0]
        else:
            base = os.path.basename(file_dir)

        self._append_log(os.path.join(file_dir, f"{base} - spectro_check.log"), log_message)

    def _append_log(self, log_path, message):
        """Append one timestamped line to a log file (no-op if logging is off).

        The timestamp lets a re-download of the same file/album leave an
        appended history rather than an ambiguous mix of old and new results.
        """
        if not self.settings['enable_logging']:
            return
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(log_path, 'a', encoding='utf-8') as log_file:
                log_file.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            self.log(f"Error writing to log file: {e}")
    
    def disable(self):
        """Clean up when plugin is disabled"""
        self.log("Stopping worker thread...")
        
        # Signal the worker to stop
        self.stop_event.set()

        # Kill any spectro process the worker is currently blocked on so disable
        # doesn't hang for up to the full subprocess timeout
        proc = self._current_proc
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except Exception as e:
                self.log(f"Could not stop running spectro process: {e}")

        # Wait for worker to finish current task
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=10)
            if self.worker_thread.is_alive():
                self.log("Warning: Worker thread did not stop cleanly")
            else:
                self.log("Worker thread stopped")

        # Emit a summary for whatever the worker managed to check before stopping
        self._flush_summaries(force=True)

        self.log("Upscale Detector disabled")