# yamcam3 - CeC September 2024
#
# camera_audio_stream.py --> audio streaming class
#
#
#  Class: CameraAudioStream - each sound source is analyzed in a separate thread
#
#  Methods:
#
#         __init__(self, camera_name, rtsp_url, analyze_callback)
#             Set up thread
#
#         start(self)
#             Start thread - set up FFMPEG to stream with proper settings
#
#         read_stderr(self)
#             Monitor stderr for messages from FFMPEG which can be informational
#             or errors, but FFMPEG does not provide a code to differentiate between them.
#
#         stop(self)
#             Stop thread
#
#         read_stream(self)
#             Continuously pull data from FFMPEG stream.  When a 31,200 byte segment
#             is in hand, convert to a form that YAMNet can classify.
#             Pass the waveform to analyze_callback (in yamnet.py) which
#             in turn calls rank_scores (in yamnet_functions.py) and returns
#             results that can be sent (via the report function in yamnet_functions.py)
#             to Home Assistant via MQTT.
#             
#        restart_process(self):
#
#        stop_ffmpeg_process(self):
#
#        start_ffmpeg_process(self):
#

import os
import subprocess
import threading
import numpy as np
import logging
import time
import tflite_runtime.interpreter as tflite
from yamcam_config import logger, model_path

class CameraAudioStream:

    def __init__(self, camera_name, rtsp_url, analyze_callback, supervisor):
        try:
            logger.info(f"Initializing CameraAudioStream: {camera_name}")
            self.camera_name = camera_name
            self.rtsp_url = rtsp_url
            self.analyze_callback = analyze_callback
            self.process = None
            self.thread = None
            self.stderr_thread = None
            self.running = False
            self.buffer_size = 31200  # YAMNet needs 15,600 samples, 2B per sample
            self.lock = threading.Lock()
            self.interpreter = tflite.Interpreter(model_path=model_path)
            self.interpreter.allocate_tensors()
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            self.supervisor = supervisor

            # ffmpeg command
            self.command = [
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

        except Exception as e:
            logger.error(f"Exception in __init__.CameraAudioStream {self.camera_name}: {e}")

    def start(self):
        with self.lock:
            if self.running:
                return  # Prevent double-starting

            try:
                self.process = subprocess.Popen(
                    self.command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0
                )
                self.running = True

                # Start threads to read from the FFmpeg stream and stderr
                self.thread = threading.Thread(target=self.read_stream, daemon=True)
                self.thread.start()
                self.stderr_thread = threading.Thread(target=self.read_stderr, daemon=True)
                self.stderr_thread.start()

                logger.info(f"START audio stream: {self.camera_name}.")

            except Exception as e:
                logger.error(f"{self.camera_name}: Exception during start: {e}", exc_info=True)
                self.running = False
                self.supervisor.stream_stopped(self.camera_name)

    # Rest of the methods remain mostly the same, removing references to should_reconnect

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
            # Wait for threads to finish
            current_thread = threading.current_thread()
            if self.thread and self.thread != current_thread:
                self.thread.join()
            if self.stderr_thread and self.stderr_thread != current_thread:
                self.stderr_thread.join()
        # Inform supervisor that the stream has stopped
        self.supervisor.stream_stopped(self.camera_name)

    # Ensure that read_stream calls self.stop() when appropriate

    def read_stream(self):
        raw_audio = b""
        while self.running:
            try:
                while len(raw_audio) < self.buffer_size:
                    fd = self.process.stdout.fileno()
                    # Wait up to 5 seconds for data to become available
                    ready, _, _ = select.select([fd], [], [], 5)
                    if ready:
                        chunk = self.process.stdout.read(self.buffer_size - len(raw_audio))
                        if not chunk:
                            # Handle EOF or process termination
                            return_code = self.process.poll()
                            if return_code is not None:
                                logger.error(f"{self.camera_name}: FFmpeg process terminated with return code {return_code}.")
                                self.stop()
                                return
                            else:
                                logger.error(f"{self.camera_name}: No data read from FFmpeg stdout, but process is still running.")
                                time.sleep(1)
                                continue
                        else:
                            raw_audio += chunk
                    else:
                        # Timeout occurred; handle accordingly
                        logger.error(f"{self.camera_name}: Timeout waiting for data from FFmpeg.")
                        self.stop()
                        return

                # Process raw_audio
                waveform = np.frombuffer(raw_audio, dtype=np.int16) / 32768.0
                waveform = np.squeeze(waveform)
                if self.analyze_callback:
                    self.analyze_callback(
                        self.camera_name,
                        waveform,
                        self.interpreter,
                        self.input_details,
                        self.output_details
                    )

            except Exception as e:
                logger.error(f"Exception in read_stream.CameraAudioStream: {self.camera_name}: {e}", exc_info=True)
                self.stop()
                return  # Exit the method to stop the thread

            finally:
                raw_audio = b""

