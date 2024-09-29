# yamcam3 - CeC September 2024
# (add streaming and threads)
#
# audio streaming class
#
import subprocess
import time
import threading
import numpy as np
import logging
import select
import yamcam_config
from yamcam_config import interpreter, input_details, output_details

logger = yamcam_config.logger

class CameraAudioStream:
    def __init__(self, camera_name, rtsp_url, analyze_callback):
        self.camera_name = camera_name
        self.rtsp_url = rtsp_url
        self.process = None
        self.thread = None
        self.running = False
        self.buffer_size = 31200  # YAMNet needs 15,600 samples, 2B per sample
        self.lock = threading.Lock()
        self.analyze_callback = analyze_callback

    def _is_non_critical_ffmpeg_log(self, log_message):
        non_critical_keywords = ['bitrate', 'speed', 'size', 'tbn', 'fps']
        return any(keyword in log_message for keyword in non_critical_keywords)

    def start(self):
        # Adjustable parameters for FFmpeg command
        command = [
            'ffmpeg',
            '-rtsp_transport', 'tcp',  # Transport mode
            '-i', self.rtsp_url,        # Input RTSP URL
            '-f', 's16le',              # Output format (raw audio)
            '-acodec', 'pcm_s16le',     # Audio codec (PCM 16-bit little-endian)
            '-ac', '1',                 # Mono audio
            '-ar', '16000',             # Sample rate: 16 kHz
            '-reorder_queue_size', '0', # Disable reordering to reduce latency
            '-use_wallclock_as_timestamps', '1',  # Use real-time timestamps
            '-probesize', '50M',        # Adjustable probesize
            '-analyzeduration', '10M',  # Adjustable analyzeduration
            '-max_delay', '500000',     # Adjustable max delay
            '-fflags', 'nobuffer',      # No buffering for low latency
            '-'
        ]

        # Start the FFmpeg process with the constructed command
        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )
        self.running = True

        # Start the stream reading thread
        self.thread = threading.Thread(target=self.read_stream, daemon=True)
        self.thread.start()

        # Start a separate thread for reading stderr
        stderr_thread = threading.Thread(target=self.read_stderr, daemon=True)
        stderr_thread.start()

        logger.info(f"{self.camera_name}: Started audio stream")

    def read_stderr(self):
        """ Read FFmpeg stderr in a separate thread """
        while self.running:
            try:
                stderr_output = self.process.stderr.read(1024).decode()
                if stderr_output and not self._is_non_critical_ffmpeg_log(stderr_output):
                    logger.error(f"{self.camera_name} - FFmpeg sderr: {stderr_output}")
            except Exception as e:
                logger.error(f"{self.camera_name}: Error reading FFmpeg stderr: {e}")

    def read_stream(self):
        logger.debug(f"{self.camera_name}: Started reading stream")

        raw_audio = b""
        logger.debug(f"{self.camera_name}: Attempting to read from stream")

        while self.running:
            try:
                while len(raw_audio) < self.buffer_size:
                    chunk = self.process.stdout.read(self.buffer_size - len(raw_audio))
                    if not chunk:
                        logger.error(f"{self.camera_name}: Failed to read additional data")
                        break
                    raw_audio += chunk
                    logger.debug(f"{self.camera_name}: Accumulated {len(raw_audio)} bytes")

                if len(raw_audio) == self.buffer_size:
                    waveform = np.frombuffer(raw_audio, dtype=np.int16) / 32768.0
                    waveform = np.squeeze(waveform)  # Ensure waveform is a 1D array
                    logger.debug(f"{self.camera_name}: Waveform length: {len(waveform)}")
                    logger.debug(f"{self.camera_name}: Segment shape: {waveform.shape}")

                    self.analyze_callback(self.camera_name, waveform)

                else:
                    logger.error(f"{self.camera_name}: Incomplete audio capture. Total buffer size: {len(raw_audio)}")

            except Exception as e:
                logger.error(f"{self.camera_name}: Error reading stream: {e}")

            raw_audio = b""  # Reset for the next capture

    def stop(self):
        with self.lock:
            if not self.running:
                return
            self.running = False
            if self.process:
                self.process.terminate()
                self.process.wait()
                self.process = None
            logger.info(f"{self.camera_name}: Stopped audio stream")

