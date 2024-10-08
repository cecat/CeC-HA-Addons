#
#
# Supervisor function to keep track of sources going offline and
# reconnecting them when they come online again
# Oct 2024
#

#    __init__(self, camera_configs, analyze_callback):
#
#
#    start_all_streams(self):
#
#
#    start_stream(self, camera_name):
#
#
#    stop_all_streams(self):
#
#
#    monitor_streams(self):
#
#
#    stream_stopped(self, camera_name):
#
#

import threading
import time
from camera_audio_stream import CameraAudioStream
from yamcam_config import logger

class CameraStreamSupervisor:
    def __init__(self, camera_configs, analyze_callback):
        self.camera_configs = camera_configs
        self.analyze_callback = analyze_callback
        self.streams = {}  # {camera_name: CameraAudioStream}
        self.lock = threading.Lock()
        self.running = True
        self.supervisor_thread = threading.Thread(target=self.monitor_streams, daemon=True)

    def start_all_streams(self):
        for camera_name, camera_config in self.camera_configs.items():
            self.start_stream(camera_name)
        self.supervisor_thread.start()
        logger.info("Supervisor thread started.")

    def start_stream(self, camera_name):
        camera_config = self.camera_configs.get(camera_name)
        if camera_config:
            rtsp_url = camera_config['ffmpeg']['inputs'][0]['path']
            try:
                stream = CameraAudioStream(camera_name, rtsp_url, self.analyze_callback, self)
                stream.start()
                self.streams[camera_name] = stream
                logger.info(f"Started stream for {camera_name}.")
            except Exeption as e:
                logger.error(f"{camera_name}: Failed to start stream {e}", exc_info=True)
        else:
            logger.error(f"{camera_name}: No configuration found.")

    def stop_all_streams(self):
        with self.lock:
            self.running = False
            # Iterate over a copy to avoid modification during iteration
            for stream in list(self.streams.values()):
                stream.stop()
            logger.info("All audio streams stopped.")
        self.supervisor_thread.join()
        logger.info("Supervisor thread stopped.")

    def monitor_streams(self):
        logger.info("Supervisor monitoring started.")
        while self.running:
            time.sleep(60)  # Sleep for 1m, make sure all streams are good, restart any dead ones
            with self.lock:
                for camera_name in self.camera_configs.keys():
                    stream = self.streams.get(camera_name)
                    if not stream or not stream.running:
                        logger.info(f"{camera_name} stream not running. Attempting to restart.")
                        self.start_stream(camera_name)
        logger.info("Supervisor monitoring stopped.")

    def stream_stopped(self, camera_name):
        logger.info(f"Stream {camera_name} has stopped.")
        # Remove the stopped stream from the dictionary
        if camera_name in self.streams:
            del self.streams[camera_name]

