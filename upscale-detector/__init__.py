"""
Nicotine+ Upscale Detector Plugin
Detects upscaled audio files after download using spectro frequency analysis
"""

import os
import json
import subprocess
import threading
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
                'description': 'Enable logging to file and cache (disables both spectro_check.log and upscale_check_cache.json)',
                'type': 'bool'
            },
            'music_directory': {
                'description': 'Path to your music directory (for individual file logging)',
                'type': 'str'
            },
        }
        
        self.checks_cache = {}
        self.pending_files = []
        self.check_thread = None
        self.cache_file = None
        
        self.log("Upscale Detector initialized")
        self._init_cache_file()
    
    def _init_cache_file(self):
        """Initialize cache file location"""
        try:
            config_dir = Path.home() / '.config' / 'nicotine'
            config_dir.mkdir(parents=True, exist_ok=True)
            self.cache_file = config_dir / 'upscale_check_cache.json'
            self._load_cache()
        except Exception as e:
            self.log(f"Warning: Could not initialize cache file: {e}")
    
    def _load_cache(self):
        """Load cached check results"""
        if self.cache_file and self.cache_file.exists() and self.settings['enable_logging']:
            try:
                with open(self.cache_file, 'r') as f:
                    self.checks_cache = json.load(f)
                self.log(f"Loaded {len(self.checks_cache)} cached check results")
            except Exception as e:
                self.log(f"Error loading cache: {e}")
    
    def _save_cache(self):
        """Save check results to cache file"""
        if self.cache_file and self.settings['enable_logging']:
            try:
                with open(self.cache_file, 'w') as f:
                    json.dump(self.checks_cache, f, indent=2)
            except Exception as e:
                self.log(f"Error saving cache: {e}")
    
    def download_finished_notification(self, user, virtual_path, real_path):
        """Called when a file download completes"""
        # Always queue audio files for checking
        if self._is_audio_file(real_path):
            self._queue_file_check(real_path)
    
    def _queue_file_check(self, filepath):
        """Queue a file for upscale checking"""
        if filepath not in self.pending_files:
            self.pending_files.append(filepath)
            self.log(f"Checking with spectro: {filepath}")
            
            if self.check_thread is None or not self.check_thread.is_alive():
                self.check_thread = threading.Thread(
                    target=self._process_check_queue,
                    daemon=True
                )
                self.check_thread.start()
    
    def _process_check_queue(self):
        """Process the queue of files to check"""
        while self.pending_files:
            filepath = self.pending_files.pop(0)
            result = self._check_file(filepath)
            if result:
                self.checks_cache[filepath] = result
                self._save_cache()
                
                status = result.get('status', 'Unknown')
                reason = result.get('reason', '')
                filename = os.path.basename(filepath)
                
                if status == 'Passed':
                    symbol = "✓"
                elif status == 'Failed':
                    symbol = "✗"
                else:
                    symbol = "!"
                
                log_message = f"{symbol} Upscale Check: [{status}] {filename} - {reason}"
                self.log(log_message)
                
                # Write to log file (skip skipped files)
                if status != 'Skipped':
                    self._write_to_log_file(filepath, log_message)
    
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
        try:
            # Get directory and filename
            file_dir = os.path.dirname(filepath)
            filename = os.path.basename(filepath)
            
            # Save current directory
            original_dir = os.getcwd()
            
            try:
                # Change to file directory
                os.chdir(file_dir)
                
                # Run spectro on the file
                cmd = ['spectro', 'check', filename]
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=60
                )
                
                # Change back to original directory
                os.chdir(original_dir)
                
                if result.returncode == 0:
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
                        self.log(f"Unexpected spectro output format: {output_line}")
                        return None
                
            finally:
                # Ensure we change back to original directory
                os.chdir(original_dir)
            
        except FileNotFoundError:
            self.log("spectro tool not found. Install: pipx install spectro")
            return None
        except subprocess.TimeoutExpired:
            self.log(f"spectro analysis timed out for {filepath}")
            return None
        except Exception as e:
            self.log(f"Error with spectro: {e}")
            return None
    
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
        if self.check_thread and self.check_thread.is_alive():
            self.check_thread.join(timeout=5)
        self._save_cache()
        self.log("Upscale Detector disabled")
