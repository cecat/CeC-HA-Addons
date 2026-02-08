#!/usr/bin/env python3
"""
camera_audio_stream.py - Camera audio stream class for Yamcam5 Home Assistant Add-on
CeC October 2024 (Updated Feb 2025 with non-blocking I/O and timeout monitoring)
"""

import threading
import subprocess
import time
import logging
import fcntl
import os
import numpy as np
import tflite_runtime.interpreter as tflite
from yamcam_config import logger, model_path, ffmpeg_debug

class CameraAudioStream:
    def __init__(self, camera_name, rtsp_url, analyze_callback, buffer_size, shutdown_event):
        self.camera_name = camera_name
        self.rtsp_url = rtsp_url
        self.analyze_callback = analyze_callback
        self.buffer_size = buffer_size
        self.shutdown_event = shutdown_event
        self.process = None
        self.command = []
        self.read_thread = None
        self.error_thread = None
        self.timeout_thread = None
        self.running = False
        self.lock = threading.Lock()
        self.ffmpeg_started_event = threading.Event()

        # Create a per-stream interpreter for Coral TPU processing.
        try:
            self.interpreter = tflite.Interpreter(model_path=model_path)
            self.interpreter.allocate_tensors()
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
        except Exception as e:
            logger.error(f"{self.camera_name}: Failed to initialize interpreter: {e}", exc_info=True)

    def start(self):
        with self.lock:
            if self.running:
                logger.warning(f"{self.camera_name}: Stream already running.")
                return
            self.running = True
            logger.debug(f"Starting audio stream for {self.camera_name}.")
            rtsp_url_with_timeout = self._construct_rtsp_url_with_timeout()
            self.command = [
                'ffmpeg',
                '-rtsp_transport', 'tcp',
                '-timeout', '30000000',
                '-i', rtsp_url_with_timeout,
                '-f', 's16le',
                '-acodec', 'pcm_s16le',
                '-ac', '1',
                '-ar', '16000',
                '-reorder_queue_size', '0',
                '-use_wallclock_as_timestamps', '1',
                '-probesize', '50M',
                '-analyzeduration', '10M',
                '-max_delay', '500000',
                '-flags', 'low_delay',
                '-fflags', 'nobuffer',
                '-'
            ]
            logger.debug(f"{self.camera_name}: FFmpeg command: {' '.join(self.command)}")
            try:
                self.process = subprocess.Popen(
                    self.command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    bufsize=0
                )
            except Exception as e:
                logger.error(f"{self.camera_name}: Failed to start FFmpeg process: {e}", exc_info=True)
                self.running = False
                return

            self._set_non_blocking(self.process.stdout)
            self._set_non_blocking(self.process.stderr)
            self.read_thread = threading.Thread(target=self.read_stream, name=f"ReadThread-{self.camera_name}")
            self.error_thread = threading.Thread(target=self.read_stderr, name=f"ErrorThread-{self.camera_name}")
            self.read_thread.start()
            self.error_thread.start()
            self.timeout_thread = threading.Thread(target=self._timeout_monitor, name=f"TimeoutThread-{self.camera_name}")
            self.timeout_thread.start()

    def _construct_rtsp_url_with_timeout(self):
        if '?' in self.rtsp_url:
            return f"{self.rtsp_url}&timeout=30000000"
        else:
            return f"{self.rtsp_url}?timeout=30000000"

    def _set_non_blocking(self, fd):
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    def _timeout_monitor(self):
        timeout_duration = 30  # seconds
        if not self.ffmpeg_started_event.wait(timeout_duration):
            logger.warning(f"{self.camera_name}: FFmpeg process did not start within {timeout_duration} seconds.")
            self.stop()
        else:
            logger.debug(f"{self.camera_name}: FFmpeg process started successfully.")

    def read_stream(self):
        raw_audio = b""
        while self.running and not self.shutdown_event.is_set():
            try:
                chunk = self.process.stdout.read(self.buffer_size - len(raw_audio))
                if chunk:
                    raw_audio += chunk
                    if len(raw_audio) >= self.buffer_size:
                        waveform = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32)
                        waveform /= 32768.0  # Normalize to [-1, 1]
                        if self.analyze_callback:
                            self.analyze_callback(waveform, self.camera_name)
                        raw_audio = b""
                else:
                    time.sleep(0.1)
            except BlockingIOError:
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"{self.camera_name}: Exception in read_stream: {e}", exc_info=True)
                break
        logger.debug(f"{self.camera_name}: Exiting read_stream.")

    def read_stderr(self):
        if not self.process or self.process.poll() is not None:
            logger.error(f"{self.camera_name}: FFmpeg process failed to start or exited unexpectedly.")
            return
        while self.running and not self.shutdown_event.is_set():
            try:
                if self.process.stderr:
                    line = self.process.stderr.readline()
                    if line:
                        self._handle_stderr_line(line)
                    else:
                        time.sleep(0.1)
                else:
                    logger.warning(f"{self.camera_name}: FFmpeg stderr unavailable.")
                    break
            except (OSError, BlockingIOError):
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"{self.camera_name}: Exception in read_stderr: {e}", exc_info=True)
                break
        logger.debug(f"{self.camera_name}: Exiting read_stderr.")

    def _handle_stderr_line(self, line):
        line_decoded = line.decode('utf-8', errors='ignore').strip()
        logger.debug(f"FFmpeg stderr ({self.camera_name}): {line_decoded}")
        if "401 Unauthorized" in line_decoded:
            logger.warning(f"{self.camera_name}: FFmpeg unauthorized access. Check credentials.")
            self.stop()
        elif "No route to host" in line_decoded:
            logger.warning(f"{self.camera_name}: No route to host. Check IP address.")
            self.stop()
        elif "Connection refused" in line_decoded:
            logger.warning(f"{self.camera_name}: Connection refused. Check port number.")
            self.stop()
        elif "403 Forbidden" in line_decoded:
            logger.warning(f"{self.camera_name}: Access denied. Check configuration.")
            self.stop()
        elif "timed out" in line_decoded:
            logger.warning(f"{self.camera_name}: Connection timed out. Check IP address.")
            self.stop()
        elif "Press [q] to stop" in line_decoded:
            logger.debug(f"{self.camera_name}: FFmpeg process started successfully.")
            self.ffmpeg_started_event.set()

    def stop(self):
        with self.lock:
            if not self.running:
                return
            self.running = False
            self.shutdown_event.set()
            logger.debug(f"{self.camera_name}: Stopping audio stream.")
            if self.process:
                try:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        logger.warning(f"{self.camera_name}: FFmpeg did not terminate in time; killing process.")
                        self.process.kill()
                        self.process.wait()
                except Exception as e:
                    logger.error(f"{self.camera_name}: Exception terminating FFmpeg: {e}", exc_info=True)
                finally:
                    if self.process.stdout:
                        self.process.stdout.close()
                    if self.process.stderr:
                        self.process.stderr.close()
                    self.process = None
            current_thread = threading.current_thread()
            if self.read_thread and self.read_thread.is_alive() and self.read_thread != current_thread:
                self.read_thread.join(timeout=5)
            if self.error_thread and self.error_thread.is_alive() and self.error_thread != current_thread:
                self.error_thread.join(timeout=5)
            if self.timeout_thread and self.timeout_thread.is_alive() and self.timeout_thread != current_thread:
                self.timeout_thread.join(timeout=5)
            logger.debug(f"{self.camera_name}: Audio stream stopped.")

