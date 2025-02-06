#!/usr/bin/env python3
#
# Yamcam Sound Profiler - CeC February 2025
# An optimization of Yamcam3 (2024)
#
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
    shutdown_event
)
import yamcam_config  # all setup and configuration happens here
from yamcam_config import logger, interpreter, input_details, output_details
from yamcam_supervisor import CameraStreamSupervisor  # Import the supervisor

# Enable faulthandler to dump stack traces on faults (helpful during debugging)
faulthandler.enable()

def dump_all_thread_traces():
    """
    Dump stack traces for all non‐current threads.
    Useful for debugging when threads seem to hang.
    """
    for thread in threading.enumerate():
        if thread == threading.current_thread():
            continue  # Skip the current thread to avoid clutter
        thread_name = thread.name
        thread_id = thread.ident
        logger.debug(f"Thread {thread_name} (ID: {thread_id}) stack trace:")
        stack = sys._current_frames()[thread_id]
        traceback.print_stack(stack)

# -----------------------------------------------------------
# Pull camera configuration from yamcam_config
# -----------------------------------------------------------
camera_settings = yamcam_config.camera_settings

# Global flag for main loop operation
running = True

# -----------------------------------------------------------
# SHUTDOWN HANDLER
# -----------------------------------------------------------
def shutdown(signum, frame):
    """
    Shutdown handler for graceful termination.
    Sets the shutdown event, stops streams, and exits the process.
    """
    global running
    logger.info(f"Received shutdown signal (signal {signum}), shutting down...")
    running = False
    shutdown_event.set()            # Signal all threads (including analysis threads) to shut down
    supervisor.shutdown_event.set() # Propagate shutdown to the supervisor as well
    supervisor.stop_all_streams()   # Request that all camera streams stop
    sys.exit(0)

# Register shutdown signals (SIGINT, SIGTERM)
signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

# -----------------------------------------------------------
# SOUND ANALYSIS CALLBACK
# -----------------------------------------------------------
def analyze_callback(waveform, camera_name):
    """
    Callback to process a waveform from a camera stream.
    It invokes YAMNet inference using a shared interpreter, ranks the scores,
    and then updates the sound window for event detection.
    """
    try:
        if shutdown_event.is_set():
            return

        # Process the waveform using the shared interpreter and model details
        scores = analyze_audio_waveform(waveform, camera_name, interpreter, input_details, output_details)
        if shutdown_event.is_set():
            return

        if scores is not None:
            results = rank_sounds(scores, camera_name)
            if shutdown_event.is_set():
                return
            # Only keep detected sounds that are part of the configured groups to track
            detected_sounds = [
                result['class']
                for result in results
                if result['class'] in yamcam_config.sounds_to_track
            ]
            update_sound_window(camera_name, detected_sounds)
        else:
            if not shutdown_event.is_set():
                logger.error(f"FAILED to analyze audio: {camera_name}")
    except Exception as e:
        logger.error(f"Exception in analyze_callback for {camera_name}: {e}", exc_info=True)

# -----------------------------------------------------------
# START UP: Initialize and start all camera streams via the supervisor
# -----------------------------------------------------------
supervisor = CameraStreamSupervisor(camera_settings, analyze_callback, shutdown_event)
supervisor.start_all_streams()

# Start a dedicated thread for periodic summary logging.
# (This thread calls log_summary which is defined in yamcam_functions.)
summary_thread = threading.Thread(target=log_summary, daemon=True, name="SummaryLogger")
summary_thread.start()
logger.debug("Summary logging thread started.")

# -----------------------------------------------------------
# MAIN LOOP
# -----------------------------------------------------------
try:
    while running and not shutdown_event.is_set():
        time.sleep(1)  # Keep the main thread alive
except KeyboardInterrupt:
    shutdown(signal.SIGINT, None)
finally:
    try:
        logger.debug("******------> STOPPING ALL audio streams...")
        supervisor.stop_all_streams()
        logger.debug("All audio streams stopped. Exiting.")

        # Attempt to join any non-daemon threads to allow graceful cleanup.
        for t in threading.enumerate():
            if t is not threading.main_thread():
                logger.debug(f"Thread still alive: {t.name}, daemon={t.daemon}")
                t.join(timeout=5)
        logging.shutdown()  # Flush all logging handlers
        sys.exit(0)
    except Exception as e:
        logger.error(f"Exception in final shutdown: {e}", exc_info=True)
        sys.exit(1)

