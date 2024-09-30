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
import yamcam_config
from yamcam_config import interpreter, input_details, output_details

logger = yamcam_config.logger

class CameraAudioStream:
    def __init__(self, camera_name, rtsp_url, analyze_callback):
        try:
            logger.debug(f"Initializing CameraAudioStream for {camera_name}")
            self.camera_name = camera_name
            self.rtsp_url = rtsp_url
            self.process = None
            self.thread = None
            self.running = False
            self.buffer_size = 31200  # YAMNet needs 15,600 samples, 2B per sample
            self.lock = threading.Lock()
            self.stderr_thread = None
            self.analyze_callback = analyze_callback  
            # Log the callback assignment
            logger.debug(f"{self.camera_name}: analyze_callback assigned: {analyze_callback}")
        except Exception as e:
            logger.error(f"Exception in CameraAudioStream __init__: {e}")

    def start(self):
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
            '-flags', 'low_delay',
            '-fflags', 'nobuffer',
            '-'
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

        # Start stderr reading thread
        self.stderr_thread = threading.Thread(target=self.read_stderr, daemon=True)
        self.stderr_thread.start()

        logger.info(f"{self.camera_name}: Started audio stream.")

    def read_stream(self):
        logger.debug(f"{self.camera_name}: Started reading stream.")

        self.buffer_size = 31200
        raw_audio = b""

        while self.running:
            try:
                while len(raw_audio) < self.buffer_size:
                    chunk = self.process.stdout.read(self.buffer_size - len(raw_audio))
                    if not chunk:
                        logger.error(f"{self.camera_name}: Failed to read additional data.")
                        break
                    raw_audio += chunk
                    #logger.debug(f"{self.camera_name}: Accumulated {len(raw_audio)} bytes.")

                if len(raw_audio) < self.buffer_size:
                    logger.error(f"{self.camera_name}: Incomplete audio capture. Total buffer size: {len(raw_audio)}")
                else:
                    logger.debug(f"{self.camera_name}: Successfully accumulated full buffer.")
                    waveform = np.frombuffer(raw_audio, dtype=np.int16) / 32768.0
                    waveform = np.squeeze(waveform)
                    if hasattr(self, 'analyze_callback') and self.analyze_callback:
                        self.analyze_callback(self.camera_name, waveform)
                    else:
                        logger.error(f"{self.camera_name}: analyze_callback is not set.")


            except Exception as e:
                logger.error(f"{self.camera_name}: Error reading stream: {e}")
                self.stop()

            finally:
                raw_audio = b""

    def read_stderr(self):
        while self.running:
            try:
                stderr_output = self.process.stderr.read(1024).decode()
                if stderr_output:
                    if not self._is_non_critical_ffmpeg_log(stderr_output):
                        logger.error(f"{self.camera_name}: FFmpeg stderr: {stderr_output}")
                    else:
                        logger.debug(f"{self.camera_name}: FFmpeg info: {stderr_output}")
            except Exception as e:
                logger.error(f"{self.camera_name}: Error reading FFmpeg stderr: {e}")

    def _is_non_critical_ffmpeg_log(self, log_message):
        non_critical_keywords = ['Stream #', 'Output #', 'size=', 'bitrate=']
            non_critical_keywords = [
                'Stream #', 'Output #', 'size=', 'bitrate=', 'frame=', 'time=', 'speed=',
                'Audio:', 'Video:', 'metadata:', 'Press [q] to stop', 'Opening',
                'configuration:', 'built with'
            ]
        return any(keyword in log_message for keyword in non_critical_keywords)

    def stop(self):
        with self.lock:
            if not self.running:
                return
            self.running = False
            if self.process:
                self.process.terminate()
                self.process.wait()
                self.process = None
            logger.info(f"{self.camera_name}: Stopped audio stream.")

