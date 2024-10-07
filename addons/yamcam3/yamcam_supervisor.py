#
#
# Supervisor function to keep track of sources going offline and
# reconnecting them when they come online again
# Oct 2024
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
        self.offline_since = {}  # {camera_name: timestamp}
        self.lock = threading.Lock()
        self.running = True
        self.supervisor_thread = threading.Thread(target=self.monitor_streams, daemon=True)

    def start_all_streams(self):
        for camera_name, camera_config in self.camera_configs.items():
            rtsp_url = camera_config['ffmpeg']['inputs'][0]['path']
            stream = CameraAudioStream(camera_name, rtsp_url, self.analyze_callback)
            stream.start()
            self.streams[camera_name] = stream
        self.supervisor_thread.start()

    def stop_all_streams(self):
        with self.lock:
            self.running = False
            for stream in self.streams.values():
                stream.stop()
            logger.info("All audio streams stopped.")
        self.supervisor_thread.join()

    def monitor_streams(self):
        while self.running:
            with self.lock:
                next_check = None  # Determine when to next run the loop
                current_time = time.time()
                for camera_name, stream in self.streams.items():
                    if not stream.running and stream.should_reconnect:
                        offline_since = self.offline_since.get(camera_name, current_time)
                        offline_duration = current_time - offline_since
                        reconnection_interval = self.calculate_reconnection_interval(offline_duration)

                        # Check if it's time to attempt reconnection
                        last_attempt = stream.last_reconnect_attempt or 0
                        if current_time - last_attempt >= reconnection_interval:
                            logger.info(f"{camera_name}: Attempting to reconnect...")
                            stream.last_reconnect_attempt = current_time
                            try:
                                stream.start()
                                stream.should_reconnect = False
                                self.offline_since.pop(camera_name, None)
                                logger.info(f"{camera_name}: Reconnection successful.")
                            except Exception as e:
                                logger.error(f"{camera_name}: Reconnection failed: {e}")
                                # If reconnection fails, offline_since remains the same
                                # so offline_duration continues to increase
                        else:
                            # Schedule the next check based on the reconnection interval
                            time_until_next_attempt = reconnection_interval - (current_time - last_attempt)
                            if next_check is None or time_until_next_attempt < next_check:
                                next_check = time_until_next_attempt
                    elif not stream.running:
                        # Stream is stopped and not marked for reconnection
                        pass
                    else:
                        # Stream is running; ensure offline_since is reset
                        self.offline_since.pop(camera_name, None)

                # Determine sleep time until the next scheduled check
                if next_check is not None:
                    sleep_time = max(1, int(next_check))
                else:
                    sleep_time = 1  # Default sleep time
            time.sleep(sleep_time)

    def calculate_reconnection_interval(self, offline_duration):
        if offline_duration < 90:
            # First 90 seconds: retry every 1 second
            return 1
        elif offline_duration < (6 * 3600):
            # Next 6 hours: retry every 60 seconds
            return 60
        else:
            # After 6 hours: retry every 600 seconds (10 minutes)
            return 600

    def stream_stopped(self, camera_name):
        with self.lock:
            self.offline_since.setdefault(camera_name, time.time())

