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
#         read_stderr(self)
#             Monitor stderr for messages from FFMPEG which can be informational
#             or errors, but FFMPEG does not provide a code to differentiate between them.

import subprocess
import threading
import numpy as np
import logging
import time
import tflite_runtime.interpreter as tflite
import select  
from yamcam_config import logger, model_path, ffmpeg_debug

class CameraAudioStream:

    def __init__(self, camera_name, rtsp_url, analyze_callback, supervisor, shutdown_event):
        try:
            logger.debug(f"Initializing CameraAudioStream: {camera_name}")
            self.camera_name = camera_name
            self.rtsp_url = rtsp_url
            self.analyze_callback = analyze_callback
            self.supervisor = supervisor
            self.shutdown_event = shutdown_event # store the shutdown event
            self.running = False
            self.buffer_size = 31200  # YAMNet needs 15,600 samples, 2B per sample
            self.lock = threading.Lock()
            self.interpreter = tflite.Interpreter(model_path=model_path)
            self.interpreter.allocate_tensors()
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            # leave these out???
            self.stderr_thread = None
            self.thread = None
            self.process = None

            # ffmpeg command
            self.command = [
                'ffmpeg',
                '-rtsp_transport', 'tcp',
                '-timeout', '30000000',    # timeout in 30s
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

# -------------- START --------------#

    def start(self):
        with self.lock:
            if self.running:
                return  # Prevent double-starting

            logger.debug(f"START audio stream: {self.camera_name}.")

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

            except Exception as e:
                logger.error(f"{self.camera_name}: Exception during start: {e}", exc_info=True)
                self.running = False
                self.supervisor.stream_stopped(self.camera_name)

# -------------- STOP --------------#

    def stop(self):
        with self.lock:
            if not self.running:
                return
            self.running = False
            if self.process:
                self.process.terminate()
                self.process.wait()
                self.process = None
            if not self.shutdown_event.is_set():
                logger.warning(f"******-->STOP audio stream: {self.camera_name}.")

            # Wait for threads to finish
            current_thread = threading.current_thread()
            if self.thread and self.thread != current_thread:
                self.thread.join()
            if self.stderr_thread and self.stderr_thread != current_thread:
                self.stderr_thread.join()
        # Inform supervisor that the stream has stopped
        self.supervisor.stream_stopped(self.camera_name)

# ----------- READ_STREM -----------#

    def read_stream(self):
        raw_audio = b""
        while self.running and not self.shutdown_event.is_set():
            try:
                while len(raw_audio) < self.buffer_size:
                    with self.lock:
                        if not self.running or not self.process or not self.process.stdout:
                            logger.error(f"{self.camera_name}: Process terminated or "
                                          "not running. Exiting read_stream.")
                            return  # Exit if the process is no longer available
                        fd = self.process.stdout.fileno()
                    # Wait up to 5 seconds for data to become available
                    ready, _, _ = select.select([fd], [], [], 5)
                    if ready:
                        chunk = self.process.stdout.read(self.buffer_size - len(raw_audio))
                        if not chunk:
                            with self.lock:
                                return_code = self.process.poll()
                            if return_code is not None:
                                logger.error(f"{self.camera_name}: FFmpeg process terminated "
                                             f"with return code {return_code}.")
                                self.stop()
                                return
                            else:
                                logger.warning(f"{self.camera_name}: No data read from FFmpeg "
                                              " stdout, but process is still running.")
                                time.sleep(0.5)
                                continue
                        else:
                            raw_audio += chunk
                    else:
                    # No data ready, select timed out
                        if self.shutdown_event.is_set() or not self.running:
                            logger.warning(f"{self.camera_name}: Shutdown detected. Exiting read_stream.")
                            return
                        else:
                            # No data yet, continue waiting for data
                            continue

                #### Process raw_audio ####

                waveform = np.frombuffer(raw_audio, dtype=np.int16) / 32768.0
                waveform = np.squeeze(waveform)
                if self.analyze_callback and not self.shutdown_event.is_set():
                    self.analyze_callback(
                        self.camera_name,
                        waveform,
                        self.interpreter,
                        self.input_details,
                        self.output_details
                    )

            except Exception as e:
                logger.error(f"{self.camera_name}: Exception in read_stream: {e}", exc_info=True)
                self.stop()
                return  # Exit the method to stop the thread

            finally:
                raw_audio = b""

# ----------- READ_STDERR -----------#

    def read_stderr(self):
        # Continuously read FFmpeg's stderr to prevent buffer blockage
        while True:
            with self.lock:
                if not self.running or not self.process or not self.process.stderr:
                    break  # Exit the loop if the stream is no longer running or process is invalid
                stderr = self.process.stderr

            try:
                line = stderr.readline()
                if line:                    # use warning since other cams may be fine
                    line_decoded = line.decode('utf-8', errors='replace').strip()
                    if "401 Unauthorized" in line_decoded: # this is not going away without fixing config
                        logger.warning(f"*****--------> FFmpeg FAILED: Invalid credentials for {self.camera_name}.")
                        logger.warning(f"*****--------> Please STOP add-on and fix config for {self.camera_name}.")
                        break
                    elif "No route to host" in line_decoded: # this might be a temporary outage
                        logger.warning(f"*****--------> FFmpeg FAILED: No route to host for {self.camera_name}.")
                        logger.warning(f"*****--------> Please check IP address for {self.camera_name}.")
                        break
                    elif "Connection refused" in line_decoded: # this could be temp or may need fixing config
                        logger.warning(f"*****--------> FFmpeg FAILED: Connection refused for {self.camera_name}.")
                        logger.warning(f"*****--------> Please check port number in path for {self.camera_name}.")
                        break
                    elif "403 Forbidden" in line_decoded: # this could be temp or may need fixing config
                        logger.warning(f"*****--------> FFmpeg FAILED: Access denied for {self.camera_name}.")
                        logger.warning(f"*****--------> Please check channel number in path for {self.camera_name}.")
                        break
                    elif "timed out" in line_decoded: # this could be temp or may need fixing config
                        logger.warning(f"*****--------> FFmpeg FAILED: connection timeout for {self.camera_name}.")
                        logger.warning(f"*****--------> Please check IP address for {self.camera_name}.")
                        break
                    elif ffmpeg_debug:
                        logger.debug(f"FFmpeg stderr: {self.camera_name}: {line_decoded}")
                else:
                    with self.lock:
                        if self.process:
                            return_code = self.process.poll()
                            if return_code is not None:
                                logger.warning(f"{self.camera_name}: FFmpeg process has "
                                             f"terminated with return code {return_code}.")
                                break  # Exit the loop as the process has terminated
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f"{self.camera_name}: Exception in read_stderr: {e}", exc_info=True)
                break

