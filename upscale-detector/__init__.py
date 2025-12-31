"""
Nicotine+ Upscale Detector Plugin
Detects upscaled audio files after download using spectro frequency analysis
"""

import os
import json
import subprocess
import threading
import queue
import re
import time
from pathlib import Path
from pynicotine.pluginsystem import BasePlugin


class Plugin(BasePlugin):
    """
    Monitors completed downloads and checks if audio files are upscaled using spectro
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.settings = {
            'enable_logging': True,
            'music_directory': str(Path.home() / 'Music'),
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
        }
        
        self.file_queue = queue.Queue()
        self.worker_thread = None
        self.stop_event = threading.Event()
        
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
                
                # Add 2 second delay before checking to ensure file is fully written
                time.sleep(2)
                
                # Verify file still exists and is readable
                if not os.path.exists(filepath):
                    self.log(f"File disappeared before check: {os.path.basename(filepath)}")
                    self.file_queue.task_done()
                    continue
                
                if not os.access(filepath, os.R_OK):
                    self.log(f"File not readable: {os.path.basename(filepath)}")
                    self.file_queue.task_done()
                    continue
                
                # Process the file
                result = self._check_file(filepath)
                if result:
                    status = result.get('status', 'Unknown')
                    reason = result.get('reason', '')
                    filename = os.path.basename(filepath)
                    file_dir = os.path.dirname(filepath)
                    
                    # Get parent folder name for display
                    parent_dir = os.path.basename(file_dir) if file_dir else ''
                    display_path = f"{parent_dir}/{filename}" if parent_dir else filename
                    
                    if status == 'Passed':
                        symbol = "✓"
                    elif status == 'Failed':
                        symbol = "✗"
                    else:
                        symbol = "!"
                    
                    # Log result with folder/filename path
                    log_message = f"{symbol} [{status}] {display_path} - {reason}"
                    self.log(log_message)
                    
                    # Write to log file (skip skipped files)
                    if status != 'Skipped':
                        self._write_to_log_file(filepath, f"{symbol} [{status}] {filename} - {reason}")
                
                # Mark task as done
                self.file_queue.task_done()
                
            except queue.Empty:
                # No files to process right now, loop will continue
                continue
            except Exception as e:
                self.log(f"Worker thread error: {e}")
                # Continue processing other files even if one fails
    
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
        original_dir = None
        try:
            # Get directory and filename
            file_dir = os.path.dirname(filepath)
            filename = os.path.basename(filepath)
            
            # Save current directory
            original_dir = os.getcwd()
            
            # Change to file directory
            os.chdir(file_dir)
            
            # Run spectro on the file with resource limits
            cmd = ['spectro', 'check', filename]
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=60
            )
            
            if result.returncode != 0:
                # Log stderr if spectro failed
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                self.log(f"spectro failed for {filename}: {error_msg}")
                return None
            
            # Parse spectro output - join all lines in case output is wrapped
            output_line = ' '.join(result.stdout.strip().split())
            
            if 'seems good' in output_line:
                # Extract bitrate if available
                bitrate_match = re.search(r'\[(\d+)\s*kbps\]', output_line)
                bitrate = bitrate_match.group(1) if bitrate_match else 'unknown'
                
                return {
                    'status': 'Passed',
                    'bitrate': bitrate,
                    'reason': f'{bitrate} kbps - frequency spectrum looks good',
                    'timestamp': time.time()
                }
            elif 'has max' in output_line and 'frequency' in output_line:
                # Extract bitrate and frequency
                bitrate_match = re.search(r'\[(\d+)\s*kbps\]', output_line)
                # Match frequency with or without "about" prefix
                freq_match = re.search(r'(?:about\s+)?(\d+)\s*Hz', output_line)
                
                bitrate = bitrate_match.group(1) if bitrate_match else 'unknown'
                frequency = freq_match.group(1) if freq_match else 'unknown'
                
                return {
                    'status': 'Failed',
                    'bitrate': bitrate,
                    'frequency': frequency,
                    'reason': f'{bitrate} kbps claimed, but max frequency {frequency} Hz - likely upscaled',
                    'timestamp': time.time()
                }
            else:
                # Output doesn't match expected format
                self.log(f"Unexpected spectro output for {filename}: {output_line}")
                return None
            
        except FileNotFoundError:
            self.log("spectro tool not found. Install: pipx install spectro")
            return None
        except subprocess.TimeoutExpired:
            self.log(f"spectro analysis timed out for {os.path.basename(filepath)}")
            return None
        except Exception as e:
            self.log(f"Error with spectro for {os.path.basename(filepath)}: {e}")
            return None
        finally:
            # Always restore directory
            if original_dir:
                try:
                    os.chdir(original_dir)
                except Exception as e:
                    self.log(f"Warning: Could not restore directory: {e}")
    
    def _is_audio_file(self, filepath):
        """Check if file is an audio file"""
        audio_extensions = {
            '.mp3', '.flac', '.ogg', '.m4a', '.aac',
            '.opus', '.wma', '.alac', '.ape', '.wav'
        }
        return os.path.splitext(filepath)[1].lower() in audio_extensions
    
    def _write_to_log_file(self, filepath, log_message):
        """Write check result to a log file
        
        For files in subdirectories (album folders): creates one log per folder with folder name
        For files in root music directory: creates one log per file with filename
        """
        if not self.settings['enable_logging']:
            return
            
        try:
            file_dir = os.path.dirname(filepath)
            filename = os.path.basename(filepath)
            filename_without_ext = os.path.splitext(filename)[0]
            music_dir = os.path.expanduser(self.settings['music_directory'])
            
            # Check if file is in root music directory or a subdirectory
            if file_dir == music_dir:
                # File is in root music directory - create log with filename
                log_filename = f"{filename_without_ext} - spectro_check.log"
                log_path = os.path.join(file_dir, log_filename)
            else:
                # File is in a subdirectory (album folder) - create log with folder name
                folder_name = os.path.basename(file_dir)
                log_filename = f"{folder_name} - spectro_check.log"
                log_path = os.path.join(file_dir, log_filename)
            
            # Write to log file (append mode)
            with open(log_path, 'a') as log_file:
                log_file.write(log_message + '\n')
                
        except Exception as e:
            self.log(f"Error writing to log file: {e}")
    
    def disable(self):
        """Clean up when plugin is disabled"""
        self.log("Stopping worker thread...")
        
        # Signal the worker to stop
        self.stop_event.set()
        
        # Wait for worker to finish current task
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=10)
            if self.worker_thread.is_alive():
                self.log("Warning: Worker thread did not stop cleanly")
            else:
                self.log("Worker thread stopped")
        
        self.log("Upscale Detector disabled")
