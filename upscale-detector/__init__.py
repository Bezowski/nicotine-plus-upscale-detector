"""
Nicotine+ Upscale Detector Plugin
Detects upscaled audio files after download
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
    Monitors completed downloads and checks if audio files are upscaled
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.settings = {
            'check_tool': 'ffprobe',
            'bitrate_tolerance': 10,
            'auto_check': True,
        }
        
        self.metasettings = {
            'check_tool': {
                'description': 'Tool to use for upscale detection',
                'type': 'dropdown',
                'options': ['ffprobe', 'true-bitrate']
            },
            'bitrate_tolerance': {
                'description': 'Bitrate variance tolerance in percentage (0-50)',
                'type': 'int',
                'minimum': 0,
                'maximum': 50
            },
            'auto_check': {
                'description': 'Automatically check files when download completes',
                'type': 'bool'
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
        if self.cache_file and self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    self.checks_cache = json.load(f)
                self.log(f"Loaded {len(self.checks_cache)} cached check results")
            except Exception as e:
                self.log(f"Error loading cache: {e}")
    
    def _save_cache(self):
        """Save check results to cache file"""
        if self.cache_file:
            try:
                with open(self.cache_file, 'w') as f:
                    json.dump(self.checks_cache, f, indent=2)
            except Exception as e:
                self.log(f"Error saving cache: {e}")
    
    def download_finished_notification(self, user, virtual_path, real_path):
        """Called when a file download completes"""
        if self.settings['auto_check']:
            self._queue_file_check(real_path)
    
    def _queue_file_check(self, filepath):
        """Queue a file for upscale checking"""
        if filepath not in self.pending_files:
            self.pending_files.append(filepath)
            tool = self.settings['check_tool']
            self.log(f"Checking with {tool}: {filepath}")
            
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
                
                self.log(f"{symbol} Upscale Check: [{status}] {filename} - {reason}")
    
    def _check_file(self, filepath):
        """
        Check if an audio file is upscaled
        Returns: {'status': 'Passed'|'Failed'|'Skipped'|'Error', 'reason': str, 'timestamp': float}
        """
        if not os.path.exists(filepath):
            return {'status': 'Error', 'reason': 'File not found', 'timestamp': time.time()}
        
        if not self._is_audio_file(filepath):
            return {'status': 'Skipped', 'reason': 'Not an audio file', 'timestamp': time.time()}
        
        try:
            declared_br = self._get_declared_bitrate(filepath)
            actual_br = self._get_actual_bitrate(filepath)
            
            if declared_br is None or actual_br is None:
                return {
                    'status': 'Error',
                    'reason': 'Could not determine bitrate',
                    'timestamp': time.time()
                }
            
            tolerance = (self.settings['bitrate_tolerance'] / 100.0) * declared_br
            difference = declared_br - actual_br
            
            result = {
                'declared_br': declared_br,
                'actual_br': actual_br,
                'difference': difference,
                'timestamp': time.time()
            }
            
            if difference > tolerance:
                result['status'] = 'Failed'
                result['reason'] = f'Actual {actual_br}kbps vs declared {declared_br}kbps'
            else:
                result['status'] = 'Passed'
                result['reason'] = f'{actual_br}kbps (within {self.settings["bitrate_tolerance"]}% tolerance)'
            
            return result
            
        except Exception as e:
            self.log(f"Error checking {filepath}: {e}")
            return {'status': 'Error', 'reason': str(e), 'timestamp': time.time()}
    
    def _get_declared_bitrate(self, filepath):
        """Extract bitrate from file metadata"""
        try:
            cmd = [
                'ffprobe', '-v', 'error',
                '-select_streams', 'a:0',
                '-show_entries', 'stream=bit_rate',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                filepath
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.stdout.strip():
                try:
                    br_bits = int(result.stdout.strip())
                    return br_bits // 1000
                except ValueError:
                    pass
            
            # Fallback: use format bitrate if stream bitrate not available
            cmd2 = [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=bit_rate',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                filepath
            ]
            result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=10)
            
            if result2.stdout.strip():
                try:
                    br_bits = int(result2.stdout.strip())
                    return br_bits // 1000
                except ValueError:
                    pass
            
            return self._extract_bitrate_from_filename(filepath)
            
        except Exception as e:
            self.log(f"Error getting declared bitrate: {e}")
            return None
    
    def _get_actual_bitrate(self, filepath):
        """Get the actual bitrate using spectrum analysis"""
        tool = self.settings['check_tool']
        
        if tool == 'true-bitrate':
            return self._check_with_true_bitrate(filepath)
        else:
            return self._check_with_ffprobe(filepath)
    
    def _check_with_true_bitrate(self, filepath):
        """Use true-bitrate tool for analysis"""
        try:
            cmd = ['true-bitrate', filepath]
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                
                for line in lines:
                    # Look for lines with "kbps" in them
                    if 'kbps' in line.lower():
                        match = re.search(r'(\d+)\s*kbps', line, re.IGNORECASE)
                        if match:
                            return int(match.group(1))
                
                # If no "kbps" line found, try to parse frequency and convert
                for line in lines:
                    if 'khz' in line.lower():
                        match = re.search(r'(\d+(?:\.\d+)?)\s*kHz', line, re.IGNORECASE)
                        if match:
                            freq = float(match.group(1))
                            # Convert frequency to approximate bitrate
                            if freq <= 11:
                                return 64
                            elif freq <= 13:
                                return 96
                            elif freq <= 15:
                                return 128
                            elif freq <= 17:
                                return 192
                            elif freq <= 19:
                                return 256
                            else:
                                return 320
            
            return None
            
        except FileNotFoundError:
            self.log("true-bitrate tool not found")
            return None
        except Exception as e:
            self.log(f"Error with true-bitrate: {e}")
            return None
    
    def _check_with_ffprobe(self, filepath):
        """Use ffprobe for bitrate analysis"""
        try:
            cmd = [
                'ffprobe', '-v', 'error',
                '-select_streams', 'a:0',
                '-show_entries', 'stream=bit_rate',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                filepath
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.stdout.strip():
                br_bits = int(result.stdout.strip())
                return br_bits // 1000
            
            return None
            
        except FileNotFoundError:
            self.log("ffprobe not found. Install: sudo apt install ffmpeg")
            return None
        except Exception as e:
            self.log(f"Error with ffprobe: {e}")
            return None
    
    def _extract_bitrate_from_filename(self, filepath):
        """Try to extract declared bitrate from filename"""
        filename = os.path.basename(filepath)
        
        patterns = [
            r'(\d{2,3})\s*kbps',
            r'\[(\d{2,3})\]',
            r'_(\d{2,3})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        return None
    
    def _is_audio_file(self, filepath):
        """Check if file is an audio file"""
        audio_extensions = {
            '.mp3', '.flac', '.ogg', '.m4a', '.aac',
            '.opus', '.wma', '.alac', '.ape', '.wav'
        }
        return os.path.splitext(filepath)[1].lower() in audio_extensions
    
    def disable(self):
        """Clean up when plugin is disabled"""
        if self.check_thread and self.check_thread.is_alive():
            self.check_thread.join(timeout=5)
        self._save_cache()
        self.log("Upscale Detector disabled")
