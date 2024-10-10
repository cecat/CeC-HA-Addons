#
# yamcam.py - CeC September 2024
#
#
# yamcam3 (streaming) - CeC September 2024
#

import time
import threading
import logging
import signal
import sys
from yamcam_functions import (
    start_mqtt, analyze_audio_waveform,
    report, rank_sounds, set_mqtt_client, update_sound_window,
    detected_sounds_history, history_lock
)
import yamcam_config  # all setup and config happens here
from yamcam_config import logger, summary_interval
from yamcam_supervisor import CameraStreamSupervisor  # Import the supervisor

#----- Global shutdown event for clean shutdown ----------#
shutdown_event = threading.Event()

#----- Initialize MQTT client ---#
mqtt_client = start_mqtt()
set_mqtt_client(mqtt_client)

#----------- PULL things we need from CONFIG -------------#
# (see config for definitions)
camera_settings = yamcam_config.camera_settings
mqtt_topic_prefix = yamcam_config.mqtt_topic_prefix

# Global variable to keep track of running state
running = True

#----------- Handle add-on stop gracefully ---------------#

def shutdown(signum, frame):
    logger.info(f"Received signal {signum}, shutting down...")
    shutdown_event.set()  # Signal all threads to shut down
    logger.info("******------> STOPPING ALL audio streams...")
    supervisor.stop_all_streams()
    time.sleep(1)  # Allow log messages to flush
    logger.info("All audio streams stopped. Exiting.")
    logging.shutdown()  # Ensure all logs are flushed
    sys.exit(0)


# Register the shutdown handler for SIGINT and SIGTERM
signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

#----------- Hub for sound stream analysis within each thread -----------#

def analyze_callback(camera_name, waveform, interpreter, input_details, output_details):
    scores = analyze_audio_waveform(waveform, camera_name, interpreter, input_details, output_details)

    if scores is not None:
        results = rank_sounds(scores, camera_name)
        detected_sounds = [
            result['class']
            for result in results
            if result['class'] in yamcam_config.sounds_to_track
        ]

        update_sound_window(camera_name, detected_sounds)
    else:
        logger.error(f"FAILED to analyze audio: {camera_name}")

def log_summary():
    while running:
        try:
            time.sleep(summary_interval * 60)  # Sleep for the specified interval
            if not running:
                break  # Exit if the shutdown flag is set

            with history_lock:
                summary_lines = []
                for camera_name, history in detected_sounds_history.items():
                    if not history:
                        summary_lines.append(f"{camera_name} : No history to report")
                        continue  # No sounds detected for this camera
                    num_sounds = len(history)
                    # Get unique sound classes detected
                    sound_classes = set(sound_class for _, sound_class in history)
                    # Sort the sound classes for consistent output
                    sound_list = ', '.join(sorted(sound_classes))
                    summary_lines.append(f"{camera_name} : {num_sounds} sounds in "
                                         f"past {summary_interval} min: {sound_list}")

                if summary_lines:
                    # Create a multi-line summary with indentation
                    formatted_summary = "\n    ".join(summary_lines)
                    logger.info(f"Summary:\n    {formatted_summary}")
                else:
                    logger.info("Summary: No history to report for any camera.")
        except Exception as e:
            logger.error(f"Exception in log_summary: {e}", exc_info=True)


############# Main #############

# Create and start streams using the supervisor
supervisor = CameraStreamSupervisor(camera_settings, analyze_callback, shutdown_event)
supervisor.start_all_streams()


# Start the summary logging thread
summary_thread = threading.Thread(target=log_summary, daemon=True)
summary_thread.start()
logger.info("Summary logging thread started.")

# Keep the main thread alive and handle shutdown cleanly
try:
    while running:
        time.sleep(1)  # Keep the main thread running
finally:
    logger.info("******------> STOPPING ALL audio streams...")
    supervisor.stop_all_streams()
    time.sleep(1) # pause for queued log messages to chirp
    logger.info("All audio streams stopped. Exiting.")
    logging.shutdown() # make sure all logs are flushed
