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

###################################

class CameraAudioStream:
    def __init__(self, camera_name, rtsp_url, analyze_callback, max_retries=5, retry_delay=5):
        self.camera_name = camera_name
        self.rtsp_url = rtsp_url
        self.analyze_callback = analyze_callback
        self.process = None
        self.thread = None
        self.running = False
        self.buffer_size = 31200  # YAMNet needs 15,600 samples, 2B per sample
        self.lock = threading.Lock()
        self.retry_count = 0
        self.max_retries = max_retries
        self.retry_delay = retry_delay  # Seconds to wait before retrying

    def start(self):
        self._run_ffmpeg()

    def _run_ffmpeg(self):
        command = [
            'ffmpeg',
            '-rtsp_transport', 'tcp',
            '-i', self.rtsp_url,
            '-f', 's16le',
            '-acodec', 'pcm_s16le',
            '-ac', '1',
            '-ar', '16000',
            '-reorder_queue_size', '0',
            '-use_wallclock_as_timestamps', '1',
            '-probesize', '50M',
            '-analyzeduration', '10M',
            '-max_delay', '500000',
            '-fflags', 'nobuffer',
            '-flags', 'low_delay',
            '-'
        ]

        logger.info(f"{self.camera_name}: Starting ffmpeg process with command: {' '.join(command)}")

        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )

        self.running = True
        self.thread = threading.Thread(target=self.read_stream, daemon=True)
        self.thread.start()

    def read_stream(self):
        logger.debug(f"{self.camera_name}: Started reading stream")
        while self.running:
            try:
                raw_audio = b""
                while len(raw_audio) < self.buffer_size:
                    chunk = self.process.stdout.read(self.buffer_size - len(raw_audio))
                    if not chunk:
                        logger.error(f"{self.camera_name}: Failed to read additional data")
                        break
                    raw_audio += chunk

                if len(raw_audio) < self.buffer_size:
                    logger.error(f"{self.camera_name}: Incomplete audio capture. Total buffer size: {len(raw_audio)}")
                    self._retry_or_stop()
                    continue

                waveform = np.frombuffer(raw_audio, dtype=np.int16) / 32768.0
                waveform = np.squeeze(waveform)

                if len(waveform) == 15600:
                    self.analyze_callback(self.camera_name, waveform)
                else:
                    logger.error(f"{self.camera_name}: Waveform size mismatch: {len(waveform)} != 15600")
                    self._retry_or_stop()

            except Exception as e:
                logger.error(f"{self.camera_name}: Error reading stream: {e}")
                self._retry_or_stop()

    def _retry_or_stop(self):
        """ Retry the stream if it fails. Stop after max retries. """
        self.retry_count += 1
        if self.retry_count > self.max_retries:
            logger.error(f"{self.camera_name}: Max retries exceeded. Stopping stream.")
            self.stop()
        else:
            logger.info(f"{self.camera_name}: Retrying stream in {self.retry_delay} seconds (attempt {self.retry_count}/{self.max_retries})")
            time.sleep(self.retry_delay)
            self._run_ffmpeg()

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

