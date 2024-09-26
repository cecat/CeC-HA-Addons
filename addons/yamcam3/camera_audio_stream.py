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
from yamcam_config import interpreter, input_details, output_details

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
        self.buffer_size = 31200  # 15,600 samples, 2 bytes per sample
        self.lock = threading.Lock()

    def start(self):
        # Adjustable parameters
        self.ffmpeg_probesize = '50M'
        self.ffmpeg_analyzeduration = '10M'
        self.ffmpeg_max_delay = '500000'
        self.ffmpeg_use_low_delay = True
        self.ffmpeg_use_nobuffer = True

        # Construct FFmpeg command with parameters
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
            '-probesize', self.ffmpeg_probesize,
            '-analyzeduration', self.ffmpeg_analyzeduration,
            '-max_delay', self.ffmpeg_max_delay,
        ]

        if self.ffmpeg_use_low_delay:
            command.extend(['-flags', 'low_delay'])
        if self.ffmpeg_use_nobuffer:
            command.extend(['-fflags', 'nobuffer'])

        command.append('-')

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


    def invoke_with_timeout(self, interpreter, timeout=5):
        def target():
            try:
                interpreter.invoke()
            except Exception as e:
                logger.error(f"Error during interpreter invocation: {e}")

        thread = threading.Thread(target=target)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            logger.error("Interpreter invocation timed out.")
            return False
        return True

    def read_stream(self):
        logger.debug(f"Started reading stream for {self.camera_name}")

        self.buffer_size = 31200  # 15,600 samples * 2 bytes per sample
        raw_audio = b""
        logger.debug(f"Attempting to read from stream for {self.camera_name}")

        while len(raw_audio) < self.buffer_size:
            chunk = self.process.stdout.read(self.buffer_size - len(raw_audio))
            if not chunk:
                logger.error(f"Failed to read additional data from {self.camera_name}")
                break
            raw_audio += chunk
            logger.debug(f"Accumulated {len(raw_audio)} bytes for {self.camera_name}")

        if len(raw_audio) < self.buffer_size:
            logger.error(f"Incomplete audio capture for {self.camera_name}. Total buffer size: {len(raw_audio)}")
        else:
            logger.debug(f"Successfully accumulated full buffer for {self.camera_name}")

        try:
            stderr_output = self.process.stderr.read(1024).decode()
            if stderr_output:
                logger.error(f"FFmpeg stderr for {self.camera_name}: {stderr_output}")
        except Exception as e:
            logger.error(f"Error reading FFmpeg stderr for {self.camera_name}: {e}")

        logger.debug(f"Read {len(raw_audio)} bytes from {self.camera_name}")

        if len(raw_audio) == self.buffer_size:
            try:
                waveform = np.frombuffer(raw_audio, dtype=np.int16) / 32768.0
                waveform = np.squeeze(waveform)
                logger.debug(f"Waveform length: {len(waveform)}")
                logger.debug(f"Segment shape: {waveform.shape}")

                if len(waveform) == 15600:
                    interpreter.set_tensor(input_details[0]['index'], waveform.astype(np.float32))

                    # Correct method call using self
                    if not self.invoke_with_timeout(interpreter):
                        logger.error("Failed to analyze audio due to interpreter timeout.")
                        return None

                    scores = interpreter.get_tensor(output_details[0]['index'])
                    logger.debug(f"Scores shape: {scores.shape}, Scores: {scores}")

                    if len(scores) == 0:
                        logger.error("No scores available for analysis.")
                        return None
                else:
                    logger.error(f"Waveform size mismatch for analysis: {len(waveform)} != 15600")

            except Exception as e:
                logger.error(f"Error during interpreter invocation: {e}")
        else:
            logger.error(f"Incomplete audio capture prevented analysis for {self.camera_name}")

        if not self.running:
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
