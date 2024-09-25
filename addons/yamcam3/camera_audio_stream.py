# yamcam3 - CeC September 2024
# (add streaming and threads)
#
# audio streaming class
#

import subprocess
import threading
import numpy as np
import logging
import yamcam_config

logger = yamcam_config.logger

###################################

class CameraAudioStream:
    def __init__(self, camera_name, rtsp_url, sample_duration, analyze_callback):
        self.camera_name = camera_name
        self.rtsp_url = rtsp_url
        self.sample_duration = sample_duration
        self.analyze_callback = analyze_callback
        self.process = None
        self.thread = None
        self.running = False
        self.buffer_size = int(16000 * sample_duration * 2)  # 16kHz, 16-bit audio
        self.lock = threading.Lock()

    def start(self):
        command = [
            'ffmpeg',
            '-fflags', 'nobuffer',
            '-flags', 'low_delay',
            '-rtsp_transport', 'tcp',
            '-probesize', '50M',
            '-analyzeduration', '10M',
            '-reorder_queue_size', '0',
            '-use_wallclock_as_timestamps', '1',
            '-i', self.rtsp_url,
            '-f', 's16le',
            '-acodec', 'pcm_s16le',
            '-ac', '1',
            '-ar', '16000',
            '-',
        ]
        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )
        self.running = True
        self.thread = threading.Thread(target=self.read_stream, daemon=True)
        self.thread.start()
        logger.info(f"Started audio stream for {self.camera_name}")

    def read_stream(self):

        logger.debug(f"Started reading stream for {self.camera_name}")

        self.buffer_size = 31200  # 16 kHz * 0.975 seconds * 2 bytes/sample

        incomplete_read_attempts = 0
        max_incomplete_attempts = 5

        while self.running:
            try:
                # Read raw audio data from the stream
                logger.debug(f"Attempting to read from stream for {self.camera_name}")
                raw_audio = self.process.stdout.read(self.buffer_size)
                logger.debug(f"Read completed for {self.camera_name}, read size: {len(raw_audio)}")

                # Capture and log FFmpeg stderr to diagnose issues
                stderr_output = self.process.stderr.read().decode()
                if stderr_output:
                    logger.error(f"FFmpeg stderr for {self.camera_name}: {stderr_output}")

                # Log the actual size read to track how much data is being received
                logger.debug(f"Read {len(raw_audio)} bytes from {self.camera_name}")

                # If the read is incomplete, increase attempts and log the details
                if not raw_audio or len(raw_audio) < self.buffer_size:
                    incomplete_read_attempts += 1
                    logger.error(f"Incomplete audio capture for {self.camera_name}. Buffer size: {len(raw_audio)}")

                    # Stop after max incomplete attempts
                    if incomplete_read_attempts >= max_incomplete_attempts:
                        logger.error(f"Stopping stream for {self.camera_name} after {max_incomplete_attempts} incomplete reads.")
                        break
                    continue

                # Reset counter if read is successful
                incomplete_read_attempts = 0

                # Convert raw audio bytes to numpy array
                waveform = np.frombuffer(raw_audio, dtype=np.int16) / 32768.0
                waveform = np.squeeze(waveform)
                logger.debug(f"Waveform length: {len(waveform)}")

                # Ensure the waveform is the exact size expected by YAMNet
                if len(waveform) == 15600:
                    self.analyze_callback(self.camera_name, waveform)
                else:
                    logger.error(f"Waveform size mismatch for analysis: {len(waveform)} != 15600")

            except Exception as e:
                logger.error(f"Error reading stream for {self.camera_name}: {e}")
                break

        self.stop()

    def stop(self):
        with self.lock:
            if not self.running:
                return
            self.running = False
            if self.process:
                self.process.terminate()
                self.process.wait()
                self.process = None
            logger.info(f"Stopped audio stream for {self.camera_name}")

