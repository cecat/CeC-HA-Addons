#!/usr/bin/env python3
"""
yamcam_supervisor.py - Supervisor for camera streams in Yamcam5 Home Assistant Add-on
CeC Feb 2025 (Updated)
"""

import threading
import time
import sys
from camera_audio_stream import CameraAudioStream
from yamcam_config import logger

class CameraStreamSupervisor:
    def __init__(self, camera_configs, analyze_callback, shutdown_event):
        self.camera_configs = camera_configs
        self.analyze_callback = analyze_callback
        self.shutdown_event = shutdown_event  # Shared shutdown event
        self.streams = {}  # Mapping: camera_name -> CameraAudioStream instance
        self.lock = threading.Lock()
        self.running = True
        self.supervisor_thread = threading.Thread(target=self.monitor_streams, daemon=True, name="SupervisorThread")

    def start_all_streams(self):
        logger.debug("Starting all camera streams.")
        for camera_name, camera_config in self.camera_configs.items():
            self.start_stream(camera_name)
        self.supervisor_thread.start()
        logger.debug("Supervisor thread started.")

    def start_stream(self, camera_name):
        camera_config = self.camera_configs.get(camera_name)
        if camera_config:
            try:
                rtsp_url = camera_config['ffmpeg']['inputs'][0]['path']
                stream = CameraAudioStream(camera_name, rtsp_url,
                                           self.analyze_callback,
                                           buffer_size=31200,
                                           shutdown_event=self.shutdown_event)
                stream.start()
                with self.lock:
                    self.streams[camera_name] = stream
                logger.info(f"Started stream for {camera_name}.")
            except Exception as e:
                logger.error(f"{camera_name}: Failed to start stream: {e}", exc_info=True)
                sys.exit(1)
        else:
            logger.error(f"{camera_name}: No configuration found. Halting add-on.")
            sys.exit(1)

    def stop_all_streams(self):
        with self.lock:
            if not self.running:
                return
            self.running = False
            if not self.shutdown_event.is_set():
                self.shutdown_event.set()
            for stream in list(self.streams.values()):
                try:
                    stream.stop()
                except Exception as e:
                    logger.error(f"Error stopping stream {stream.camera_name}: {e}", exc_info=True)
            logger.info("All camera streams have been requested to stop.")
        try:
            self.supervisor_thread.join(timeout=5)
            logger.info("Supervisor thread stopped.")
        except Exception as e:
            logger.error(f"Error stopping supervisor thread: {e}", exc_info=True)

    def monitor_streams(self):
        logger.debug("Supervisor monitoring started.")
        while self.running and not self.shutdown_event.is_set():
            time.sleep(60)
            with self.lock:
                for camera_name in self.camera_configs.keys():
                    if self.shutdown_event.is_set():
                        break
                    stream = self.streams.get(camera_name)
                    if not stream or not stream.running:
                        logger.warning(f"{camera_name} stream not running. Attempting to restart.")
                        self.start_stream(camera_name)
        if not self.shutdown_event.is_set():
            logger.debug("Supervisor monitoring stopped.")

    def stream_stopped(self, camera_name):
        logger.warning(f"Stream {camera_name} has stopped.")
        with self.lock:
            if camera_name in self.streams:
                del self.streams[camera_name]

