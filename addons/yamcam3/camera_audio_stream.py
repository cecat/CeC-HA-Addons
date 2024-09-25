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
            '-rtsp_transport', 'tcp',
            '-i', self.rtsp_url,
            '-f', 's16le',
            '-acodec', 'pcm_s16le',
            '-ac', '1',
            '-ar', '16000',
            '-'
        ]
        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0
        )
        self.running = True
        self.thread = threading.Thread(target=self.read_stream, daemon=True)
        self.thread.start()
        logger.info(f"Started audio stream for {self.camera_name}")

    def read_stream(self):
        while self.running:
            try:
                raw_audio = self.process.stdout.read(self.buffer_size)
                if not raw_audio:
                    break
                # Convert raw audio bytes to numpy array
                waveform = np.frombuffer(raw_audio, dtype=np.int16) / 32768.0
                # Call the analyze callback
                self.analyze_callback(self.camera_name, waveform)
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

