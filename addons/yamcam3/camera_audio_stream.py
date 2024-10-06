# yamcam3 - CeC September 2024
#
# camera_audio_stream.py --> audio streaming class
#
#
#  Class: CameraAudioStream - each sound source is analyzed in a separate thread
#
#  Methods:
#
#         def __init__(self, camera_name, rtsp_url, analyze_callback)
#             Set up thread
#
#         def start(self)
#             Start thread - set up FFMPEG to stream with proper settings
#
#         def read_stderr(self)
#             Monitor stderr for messages from FFMPEG which can be informational
#             or errors, but FFMPEG does not provide a code to differentiate between them.
#
#         def stop(self)
#             Stop thread
#
#         def read_stream(self)
#             Continuously pull data from FFMPEG stream.  When a 31,200 byte segment
#             is in hand, convert to a form that YAMNet can classify.
#             Pass the waveform to analyze_callback (in yamnet.py) which
#             in turn calls rank_scores (in yamnet_functions.py) and returns
#             results that can be sent (via the report function in yamnet_functions.py)
#             to Home Assistant via MQTT.
#             
#

import subprocess
import threading
import numpy as np
import logging
import time
import tflite_runtime.interpreter as tflite
from yamcam_config import logger, model_path

class CameraAudioStream:

    def __init__(self, camera_name, rtsp_url, analyze_callback):
        try:
            logger.info(f"Initializing CameraAudioStream: {camera_name}")
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
            self.analyze_callback = analyze_callback
        except Exception as e:
            logger.error(f"Exception in __init__.CameraAudioStream {self.camera_name}: {e}")

    def start(self):
        with self.lock:
            if self.running:
                return  # Prevent double-starting

            # construct the FFMPEG command to stream audio from the RTSP path
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

                # Start this thread to read from the FFMPEG stream 
                self.thread = threading.Thread(target=self.read_stream, daemon=True)
                self.thread.start()
                self.stderr_thread = threading.Thread(target=self.read_stderr, daemon=True)
                self.stderr_thread.start()

                logger.info(f"START audio stream: {self.camera_name}.")

            except Exception as e:
                logger.error(f"Exception in start.CameraAudioStream: {self.camera_name}: {e}")
                self.running = False

    def read_stderr(self):
        while self.running:
            try:
                stderr_output = self.process.stderr.read(1024).decode()
                if stderr_output:
                    logger.debug(f"FFmpeg stderr: {self.camera_name}:  {stderr_output}")
            except Exception as e:
                logger.error(f"Exception in read-stderr.CameraAudioStream: {self.camera_name}: {e}")

    def stop(self):
        with self.lock:
            if not self.running:
                return
            self.running = False
            if self.process:
                self.process.terminate()
                self.process.wait()
                self.process = None
            logger.info(f"******-->STOP audio stream: {self.camera_name}.")

    def OLD_read_stream(self):
        raw_audio = b""

        while self.running:
            try:
                while len(raw_audio) < self.buffer_size:
                    chunk = self.process.stdout.read(self.buffer_size - len(raw_audio))
                    if not chunk:
                        logger.error(f"Exception in read_stream.CameraAudioStream: {self.camera_name}: Failed to read additional data.")

                        break
                    raw_audio += chunk

                if len(raw_audio) < self.buffer_size:
                    logger.error(f"--->{self.camera_name}: Incomplete audio capture. Total buffer size: {len(raw_audio)}")
                else:
                    waveform = np.frombuffer(raw_audio, dtype=np.int16) / 32768.0
                    waveform = np.squeeze(waveform)
                    if self.analyze_callback:
                        self.analyze_callback(self.camera_name, waveform, self.interpreter, self.input_details, self.output_details)


            except Exception as e:
                logger.error(f"Exception in read_stream.CameraAudioStream: {self.camera_name}: {e}")
                logger.error(f"--->{self.camera_name}: Error reading stream: {e}")
                self.stop()

            finally:
                raw_audio = b""

import time  # Make sure to import time for sleep functionality

class CameraAudioStream:
    # ... existing methods ...

    def read_stream(self):
        raw_audio = b""
        restart_attempts = 0
        max_restarts = 5
        restart_delay = 5  # seconds

        while self.running:
            try:
                while len(raw_audio) < self.buffer_size:
                    chunk = self.process.stdout.read(self.buffer_size - len(raw_audio))
                    if not chunk:
                        # Check if process is still running
                        return_code = self.process.poll()
                        if return_code is not None:
                            logger.error(f"{self.camera_name}: FFmpeg process terminated with return code {return_code}. Attempting to restart.")
                            restart_attempts += 1
                            if restart_attempts <= max_restarts:
                                self.restart_process()
                                time.sleep(restart_delay)
                                raw_audio = b""  # Reset raw_audio before retrying
                                break  # Break inner loop to restart reading
                            else:
                                logger.error(f"{self.camera_name}: Max restart attempts reached ({max_restarts}). Stopping stream.")
                                self.stop()
                                return
                        else:
                            logger.error(f"{self.camera_name}: No data read from FFmpeg stdout, but process is still running.")
                            # Optionally, you might want to restart here as well
                            break
                    else:
                        raw_audio += chunk

                if len(raw_audio) < self.buffer_size:
                    logger.error(f"--->{self.camera_name}: Incomplete audio capture. Total buffer size: {len(raw_audio)}")
                else:
                    waveform = np.frombuffer(raw_audio, dtype=np.int16) / 32768.0
                    waveform = np.squeeze(waveform)
                    if self.analyze_callback:
                        self.analyze_callback(self.camera_name, waveform, self.interpreter, self.input_details, self.output_details)
                    # Reset restart attempts after successful read
                    restart_attempts = 0

            except Exception as e:
                logger.error(f"Exception in read_stream.CameraAudioStream: {self.camera_name}: {e}")
                logger.error(f"--->{self.camera_name}: Error reading stream: {e}")
                self.stop()
                return  # Exit the method to stop the thread

            finally:
                raw_audio = b""

    def restart_process(self):
        self.stop_ffmpeg_process()
        time.sleep(1)  # Short delay before restarting
        self.start_ffmpeg_process()
        logger.info(f"{self.camera_name}: FFmpeg process restarted.")

    def stop_ffmpeg_process(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(f"{self.camera_name}: FFmpeg process did not terminate. Killing process.")
                self.process.kill()
                self.process.wait()
            self.process = None

    def start_ffmpeg_process(self):
        # Reinitialize the FFmpeg process
        self.process = subprocess.Popen(
            self.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=10**8
        )

