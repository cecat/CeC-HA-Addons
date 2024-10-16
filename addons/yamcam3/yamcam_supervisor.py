#
# Supervisor function to keep track of sources going offline and
# reconnecting them when they come online again
# Oct 2024
#
#    __init__(self, camera_configs, analyze_callback):
#
#    start_all_streams(self):
#
#    start_stream(self, camera_name):
#
#    stop_all_streams(self):
#
#    monitor_streams(self):
#
#    stream_stopped(self, camera_name):
#
# yamcam_supervisor.py

import threading
import time
from camera_audio_stream import CameraAudioStream
from yamcam_config import logger

#                                              #
### ------ CLASS FOR CAM STREAMS/THREADS ----###
#                                              #

class CameraStreamSupervisor:
    
     # -------- INIT 
    def __init__(self, camera_configs, analyze_callback, shutdown_event):
        self.camera_configs = camera_configs
        self.analyze_callback = analyze_callback
        self.shutdown_event = shutdown_event # Store the shutdown event
        self.streams = {}  # {camera_name: CameraAudioStream}
        self.lock = threading.Lock()
        self.running = True
        self.supervisor_thread = threading.Thread(target=self.monitor_streams, daemon=True)

     # -------- START ALL STREAMS
    def start_all_streams(self):
        for camera_name, camera_config in self.camera_configs.items():
            self.start_stream(camera_name)
        self.supervisor_thread.start()
        logger.info("Supervisor thread started.")

     # -------- START STREAM
# -------- START STREAM
    def start_stream(self, camera_name):
        camera_config = self.camera_configs.get(camera_name)

        if camera_config:
            try:
                # Check if 'ffmpeg' and 'inputs' exist and contain the necessary data
                ffmpeg_config = camera_config.get('ffmpeg')
                if not ffmpeg_config or not isinstance(ffmpeg_config, dict):
                    raise ValueError(f"{camera_name}: 'ffmpeg' section missing or invalid in the configuration.")

                inputs = ffmpeg_config.get('inputs')
                if not inputs or not isinstance(inputs, list) or len(inputs) == 0:
                    raise ValueError(f"{camera_name}: 'inputs' section missing or invalid in the 'ffmpeg' configuration.")

                rtsp_url = inputs[0].get('path')
                if not rtsp_url or not isinstance(rtsp_url, str):
                    raise ValueError(f"{camera_name}: RTSP path is missing or invalid in the configuration.")

                # Start the stream if the path is valid
                stream = CameraAudioStream(camera_name, rtsp_url,
                                           self.analyze_callback, self, self.shutdown_event)
                stream.start()
                self.streams[camera_name] = stream
                logger.info(f"Started stream for {camera_name}.")
            except (KeyError, IndexError, TypeError, ValueError) as e:
                logger.error(f"{camera_name}: Invalid camera configuration: {e}. Halting the program.", exc_info=True)
                raise ValueError(f"Configuration error for camera '{camera_name}'. Halting the program.")
            except Exception as e:
                logger.error(f"{camera_name}: Failed to start stream: {e}. Halting the program.", exc_info=True)
                raise e
        else:
            logger.error(f"{camera_name}: No configuration found. Halting the program.")
            raise ValueError(f"Missing configuration for camera '{camera_name}'. Halting the program.")


     # -------- STOP ALL STREAMS
    def stop_all_streams(self):
        with self.lock:
            if not self.running:
                return  # Already stopped
            self.running = False
            if not self.shutdown_event.is_set():
                self.shutdown_event.set()  # Set shutdown flag
                logger.info("******------> STOPPING ALL audio streams...")
            # Iterate over a copy to avoid modification during iteration
            for stream in list(self.streams.values()):
                try:
                    stream.stop()
                except Exception as e:
                    logger.error(f"Error stopping stream {stream.camera_name}: {e}", exc_info=True)
            logger.info("All audio streams have been requested to stop.")
        try:
            self.supervisor_thread.join(timeout=5)  # Wait up to 5 seconds for supervisor_thread to finish
            logger.info("Supervisor thread stopped.")
        except Exception as e:
            logger.error(f"Error stopping supervisor thread: {e}", exc_info=True)

     # -------- MONITOR STREAMS
    def monitor_streams(self):
        logger.info("Supervisor monitoring started.")
        while self.running and not self.shutdown_event.is_set():
            time.sleep(60)  # Sleep for 1 minute
            with self.lock:
                for camera_name in self.camera_configs.keys():
                    if self.shutdown_event.is_set():
                        break
                    stream = self.streams.get(camera_name)
                    if not stream or not stream.running:
                        logger.info(f"{camera_name} stream not running. Attempting to restart.")
                        self.start_stream(camera_name)
        if not self.shutdown_event.is_set():
            logger.info("Supervisor monitoring stopped.")

     # -------- STREAM STOPPED
    def stream_stopped(self, camera_name):
        logger.info(f"Stream {camera_name} has stopped.")
        # Remove the stopped stream from the dictionary
        with self.lock:
            if camera_name in self.streams:
                del self.streams[camera_name]

