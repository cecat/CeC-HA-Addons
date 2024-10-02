# yamcam3 - CeC September 2024
# (add streaming and threads)
#
# camera_audio_stream.py
#
# audio streaming class
#

import subprocess
import time
import threading
import numpy as np
import logging
import yamcam_config
from yamcam_config import interpreter, input_details, output_details, tflite

logger = yamcam_config.logger

class CameraAudioStream:

    def __init__(self, camera_name, rtsp_url, analyze_callback):
        try:
            logger.info(f"Initializing CameraAudioStream for {camera_name}")
            self.interpreter = tflite.Interpreter(model_path=model_path)
            self.interpreter.allocate_tensors()
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            self.camera_name = camera_name
            self.rtsp_url = rtsp_url
            self.process = None
            self.thread = None
            self.running = False
            self.buffer_size = 31200  # YAMNet needs 15,600 samples, 2B per sample
            self.lock = threading.Lock()
            self.stderr_thread = None
            self.analyze_callback = analyze_callback
        except Exception as e:
            logger.error(f"Exception in CameraAudioStream __init__: {e}")

    def start(self):
        with self.lock:
            if self.running:
                return  # Prevent double-starting

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

            try:
                self.process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0
                )
                self.running = True

                # Start the reading threads
                self.thread = threading.Thread(target=self.read_stream, daemon=True)
                self.thread.start()
                self.stderr_thread = threading.Thread(target=self.read_stderr, daemon=True)
                self.stderr_thread.start()

                logger.info(f"{self.camera_name}: Started audio stream.")

            except Exception as e:
                logger.error(f"{self.camera_name}: Failed to start FFmpeg process: {e}")
                self.running = False

    def read_stderr(self):
        while self.running:
            try:
                stderr_output = self.process.stderr.read(1024).decode()
                if stderr_output:
                    logger.debug(f"{self.camera_name}: FFmpeg stderr: {stderr_output}")
            except Exception as e:
                logger.error(f"{self.camera_name}: Error reading FFmpeg stderr: {e}")
            # No lock needed here as this is an independent read operation

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

    def read_stream(self):
        # Only lock where necessary for shared resources like self.running or self.process
        raw_audio = b""
        buffer_size = self.buffer_size  # No need to lock this

        while self.running:
            try:
                while len(raw_audio) < buffer_size:
                    chunk = self.process.stdout.read(buffer_size - len(raw_audio))
                    if not chunk:
                        logger.error(f"{self.camera_name}: Failed to read additional data.")
                        break
                    raw_audio += chunk

                if len(raw_audio) < buffer_size:
                    logger.error(f"{self.camera_name}: Incomplete audio capture. Total buffer size: {len(raw_audio)}")
                else:
                    waveform = np.frombuffer(raw_audio, dtype=np.int16) / 32768.0
                    waveform = np.squeeze(waveform)
                    if self.analyze_callback:
                        #self.analyze_callback(self.camera_name, waveform)
                        self.analyze_callback(self.camera_name, waveform, self.interpreter, self.input_details, self.output_details)


            except Exception as e:
                logger.error(f"{self.camera_name}: Error reading stream: {e}")
                self.stop()

            finally:
                raw_audio = b""

