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
#    stop_all_streams(self):
#
#
#    monitor_streams(self):
#
#
#    calculate_reconnection_interval(self, offline_duration):
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
        self.offline_since = {}  # {camera_name: timestamp}
        self.lock = threading.Lock()
        self.running = True
        self.supervisor_thread = threading.Thread(target=self.monitor_streams, daemon=True)

    def start_all_streams(self):
        for camera_name, camera_config in self.camera_configs.items():
            rtsp_url = camera_config['ffmpeg']['inputs'][0]['path']
            stream = CameraAudioStream(camera_name, rtsp_url, self.analyze_callback, self)
            stream.start()
            self.streams[camera_name] = stream
        self.supervisor_thread.start()
        logger.info("Supervisor thread started.")


    def stop_all_streams(self):
        with self.lock:
            self.running = False
            for stream in self.streams.values():
                stream.stop()
            logger.info("All audio streams stopped.")
        self.supervisor_thread.join()
        logger.info("Supervisor thread stopped.")


    def monitor_streams(self):
        logger.info("Supervisor monitoring started.")
        while self.running:
            try:
                with self.lock:
                    next_check = None  # Determine when to next run the loop
                    current_time = time.time()
                    for camera_name, stream in self.streams.items():
                        if not stream.running and stream.should_reconnect:
                            offline_since = self.offline_since.get(camera_name)
                            if offline_since is None:
                                offline_since = current_time
                                self.offline_since[camera_name] = offline_since
                                logger.debug(f"{camera_name}: Marked as offline at {offline_since}")

                            offline_duration = current_time - offline_since
                            reconnection_interval = self.calculate_reconnection_interval(offline_duration)
                            if offline_duration == 90:
                                logger.info(f"{camera_name}: Drop to 1m retry interval after 90s offline.")
                            elif offline_duration == 6 * 3600:
                                logger.info(f"{camera_name}: Drop to 10m retry interval after 6h offline.")


                            last_attempt = stream.last_reconnect_attempt or 0
                            time_since_last_attempt = current_time - last_attempt

                            if time_since_last_attempt >= reconnection_interval:
                                logger.info(f"{camera_name}: Attempting to reconnect...")
                                stream.last_reconnect_attempt = current_time
                                try:
                                    stream.start()
                                    if stream.running:
                                        stream.should_reconnect = False
                                        self.offline_since.pop(camera_name, None)
                                        logger.info(f"{camera_name}: Reconnection successful.")
                                    else:
                                        logger.error(f"{camera_name}: Reconnection failed to start the stream.")
                                except Exception as e:
                                    logger.error(f"{camera_name}: Reconnection failed: {e}")
                                    # Ensure should_reconnect remains True
                                    stream.should_reconnect = True
                            else:
                                time_until_next_attempt = reconnection_interval - time_since_last_attempt
                                logger.debug(f"{camera_name}: Next reconnection attempt in "
                                             f"{time_until_next_attempt:.2f} seconds.")
                                if next_check is None or time_until_next_attempt < next_check:
                                    next_check = time_until_next_attempt
                        elif not stream.running:
                            # Stream is stopped and not marked for reconnection
                            logger.debug(f"{camera_name}: Stream is stopped and not marked for reconnection.")
                        else:
                            # Stream is running; ensure offline_since is reset
                            self.offline_since.pop(camera_name, None)

                    # Determine sleep time until the next scheduled check
                    if next_check is not None:
                        sleep_time = max(1, int(next_check))
                    else:
                        sleep_time = 1  # Default sleep time
                time.sleep(sleep_time)
            except Exception as e:
                logger.error(f"Exception in supervisor monitor_streams: {e}", exc_info=True)
                time.sleep(1)  # Prevent tight loop on exception

        logger.info("Supervisor monitoring stopped.")


    def calculate_reconnection_interval(self, offline_duration):
        if offline_duration < 90:
            return 1
        elif offline_duration < (6 * 3600):
            if not hasattr(self, 'logged_90_seconds'):
                logger.info(f"Switching to 60-second retry interval after 90 seconds offline.")
                self.logged_90_seconds = True
            return 60
        else:
            if not hasattr(self, 'logged_6_hours'):
                logger.info(f"Switching to 10-minute retry interval after 6 hours offline.")
                self.logged_6_hours = True
            return 600


    def stream_stopped(self, camera_name):
        with self.lock:
            current_time = time.time()
            if camera_name not in self.offline_since:
                self.offline_since[camera_name] = current_time
                logger.debug(f"{camera_name}: Marked as offline at {self.offline_since[camera_name]}")

