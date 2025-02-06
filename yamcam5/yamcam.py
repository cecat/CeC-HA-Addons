#!/usr/bin/env python3
#
# yamcam5 - Home Assistant Add-on (Updated Feb 2025)
# yamcam.py
#

import time
import threading
import logging
import signal
import sys
import traceback
import faulthandler

from yamcam_functions import (
    analyze_audio_waveform,
    rank_sounds,
    update_sound_window,
    log_summary,
    start_mqtt,
    set_mqtt_client,
    shutdown_event
)
import yamcam_config  # configuration, logging, model, and settings
from yamcam_config import logger, interpreter, input_details, output_details, camera_settings
from yamcam_supervisor import CameraStreamSupervisor

# Enable faulthandler for dumping stack traces if needed.
faulthandler.enable()

# --- Initialize MQTT (for reporting to Home Assistant) ---
mqtt_client = start_mqtt()
set_mqtt_client(mqtt_client)

# (Optional) A helper to dump all thread stack traces for debugging.
def dump_all_thread_traces():
    for thread in threading.enumerate():
        if thread == threading.current_thread():
            continue
        thread_name = thread.name
        thread_id = thread.ident
        logger.debug(f"Thread {thread_name} (ID: {thread_id}) stack trace:")
        stack = sys._current_frames()[thread_id]
        traceback.print_stack(stack)

running = True

def shutdown(signum, frame):
    global running
    logger.warning(f"Received shutdown signal (signal {signum}). Shutting down...")
    running = False
    shutdown_event.set()
    supervisor.shutdown_event.set()
    supervisor.stop_all_streams()
    sys.exit(0)

# Register SIGINT and SIGTERM for graceful shutdown.
signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

def analyze_callback(waveform, camera_name):
    """
    Processes an audio waveform from a camera stream:
      • Runs inference using the shared global TPU interpreter.
      • Ranks the results and filters to the configured sound groups.
      • Updates the sound event window.
    """
    try:
        if shutdown_event.is_set():
            return

        # Use the global TPU interpreter (from yamcam_config) to analyze the waveform.
        scores = analyze_audio_waveform(waveform, camera_name, interpreter, input_details, output_details)
        if shutdown_event.is_set():
            return

        if scores is not None:
            results = rank_sounds(scores, camera_name)
            if shutdown_event.is_set():
                return
            detected_sounds = [
                result['class']
                for result in results
                if result['class'] in yamcam_config.sounds_to_track
            ]
            update_sound_window(camera_name, detected_sounds)
        else:
            if not shutdown_event.is_set():
                logger.error(f"FAILED to analyze audio for camera {camera_name}.")
    except Exception as e:
        logger.error(f"Exception in analyze_callback for {camera_name}: {e}", exc_info=True)

# --- Create and start the supervisor to manage all camera streams ---
supervisor = CameraStreamSupervisor(camera_settings, analyze_callback, shutdown_event)
supervisor.start_all_streams()

# --- Start a summary logging thread (periodically logs sound event summaries) ---
summary_thread = threading.Thread(target=log_summary, daemon=True, name="SummaryLogger")
summary_thread.start()
logger.debug("Summary logging thread started.")

# --- Main Loop ---
try:
    while running and not shutdown_event.is_set():
        time.sleep(1)
except KeyboardInterrupt:
    shutdown(signal.SIGINT, None)
finally:
    try:
        logger.debug("******------> STOPPING ALL audio streams...")
        supervisor.stop_all_streams()
        logger.debug("All audio streams stopped. Exiting.")

        # Join non-daemon threads for graceful cleanup.
        for t in threading.enumerate():
            if t is not threading.main_thread():
                logger.debug(f"Thread still alive: {t.name} (daemon={t.daemon})")
                t.join(timeout=5)
        logging.shutdown()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Exception during final shutdown: {e}", exc_info=True)
        sys.exit(1)

