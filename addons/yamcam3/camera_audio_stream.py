# yamcam3 - CeC September 2024
# (add streaming and threads)
# camera_audio_stream.py - Audio streaming class for YamCam

import subprocess
import threading
import numpy as np
import logging
import yamcam_config

logger = yamcam_config.logger

class CameraAudioStream:
    def __init__(self, camera_name, rtsp_url, analyze_callback):
        self.camera_name = camera_name
        self.rtsp_url = rtsp_url
        self.analyze_callback = analyze_callback
        self.process = None
        self.thread = None
        self.running = False
        self.buffer_size = 31200  # 15,600 samples * 2 bytes per sample
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
            '-probesize', '50M',
            '-analyzeduration', '10M',
            '-flags', 'low_delay',
            '-fflags', 'nobuffer',
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
        raw_audio = b""
        while len(raw_audio) < self.buffer_size:
            chunk = self.process.stdout.read(self.buffer_size - len(raw_audio))
            if not chunk:
                logger.error(f"Failed to read additional data from {self.camera_name}")
                break
            raw_audio += chunk
            logger.debug(f"Accumulated {len(raw_audio)} bytes for {self.camera_name}")

        if len(raw_audio) == self.buffer_size:
            self.analyze_callback(self.camera_name, raw_audio)
        else:
            logger.error(f"Incomplete audio capture prevented analysis for {self.camera_name}")

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

